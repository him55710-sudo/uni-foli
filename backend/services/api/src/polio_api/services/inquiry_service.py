from __future__ import annotations

from datetime import datetime, timezone
import logging
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from sqlalchemy.orm import Session

from polio_api.core.config import Settings, get_settings
from polio_api.core.security import sanitize_public_error
from polio_api.db.models.inquiry import Inquiry
from polio_api.schemas.inquiry import InquiryCreate
from polio_api.services.prompt_registry import PromptRegistryError, get_prompt_registry

TRIAGE_PROMPT_NAME = "inquiry-support.contact-triage"
_INQUIRY_LOGGER = logging.getLogger("polio.api.inquiries")
_SMTP_TIMEOUT_SECONDS = 20.0
_SMTP_DISABLED_REASON = "SMTP_ENABLED=false"
_GENERIC_INQUIRY_DELIVERY_FAILURE = "Inquiry email delivery failed. Retry after checking SMTP configuration."
_FABRICATION_PATTERN = re.compile(r"\b(make up|fabricat(?:e|ed|ion)|조작|거짓|허위)\b", re.IGNORECASE)
_GUARANTEE_PATTERN = re.compile(r"\b(guarantee|guaranteed|100%|합격 보장|확정 합격)\b", re.IGNORECASE)
_SENSITIVE_PATTERN = re.compile(
    r"(\b\d{6}\s*[-]?\s*[1-4]\d{6}\b|\b01[016789][- ]?\d{3,4}[- ]?\d{4}\b)",
    re.IGNORECASE,
)


def create_inquiry(db: Session, payload: InquiryCreate) -> Inquiry:
    inquiry = Inquiry(
        inquiry_type=payload.inquiry_type,
        status="received",
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        subject=payload.subject,
        message=payload.message,
        inquiry_category=payload.inquiry_category,
        institution_name=payload.institution_name,
        institution_type=payload.institution_type,
        source_path=payload.source_path,
        extra_fields=_build_extra_fields(payload),
    )
    db.add(inquiry)
    db.commit()
    db.refresh(inquiry)

    from polio_api.services.async_job_service import create_async_job, dispatch_job_if_enabled
    from polio_domain.enums import AsyncJobType

    try:
        job = create_async_job(
            db,
            job_type=AsyncJobType.INQUIRY_EMAIL.value,
            resource_type="inquiry",
            resource_id=inquiry.id,
            project_id=None,
            payload={"inquiry_id": inquiry.id},
        )
    except Exception as exc:  # noqa: BLE001
        reason = sanitize_public_error(
            str(exc),
            fallback="Inquiry was saved, but email queueing failed. Check async job configuration.",
        )
        _INQUIRY_LOGGER.exception("Inquiry email queueing failed. inquiry_id=%s error=%s", inquiry.id, exc)
        _set_delivery_status(
            inquiry,
            status="failed",
            reason=reason,
            retry_needed=True,
        )
        inquiry.status = "delivery_failed"
        db.add(inquiry)
        db.commit()
        db.refresh(inquiry)
        return inquiry

    _set_delivery_status(
        inquiry,
        status="queued",
        async_job_id=job.id,
        retry_needed=False,
    )
    inquiry.status = "delivery_queued"
    db.add(inquiry)
    db.commit()
    db.refresh(inquiry)

    try:
        dispatch_job_if_enabled(job.id)
    except Exception as exc:  # noqa: BLE001
        # Job is persisted and can be picked up by worker/inline processor later.
        _INQUIRY_LOGGER.exception(
            "Inquiry email dispatch trigger failed, but job remains queued. inquiry_id=%s job_id=%s error=%s",
            inquiry.id,
            job.id,
            exc,
        )
        _set_delivery_status(
            inquiry,
            status="queued",
            reason="Delivery job queued; dispatcher trigger failed. Worker retry is required.",
            async_job_id=job.id,
            retry_needed=True,
        )
        db.add(inquiry)
        db.commit()
        db.refresh(inquiry)

    return inquiry


def send_inquiry_email_notification(db: Session, inquiry_id: str) -> None:
    inquiry = db.get(Inquiry, inquiry_id)
    if inquiry is None:
        raise ValueError(f"Inquiry not found: {inquiry_id}")

    delivery = _delivery_state(inquiry)
    if delivery.get("status") == "sent":
        _INQUIRY_LOGGER.info("Skipping inquiry email send; already sent. inquiry_id=%s", inquiry.id)
        return

    payload = _build_payload_from_inquiry(inquiry)
    settings = get_settings()
    skip_reason = _get_smtp_skip_reason(settings)
    if skip_reason is not None:
        if skip_reason == _SMTP_DISABLED_REASON:
            _INQUIRY_LOGGER.warning(
                "Skipping inquiry email notification because SMTP is disabled. inquiry_id=%s",
                inquiry.id,
            )
            _set_delivery_status(
                inquiry,
                status="skipped",
                reason=skip_reason,
                retry_needed=False,
            )
            inquiry.status = "delivery_skipped"
            db.add(inquiry)
            db.commit()
            return
        _set_delivery_status(
            inquiry,
            status="failed",
            reason=skip_reason,
            retry_needed=True,
        )
        inquiry.status = "delivery_failed"
        db.add(inquiry)
        db.commit()
        raise ValueError(skip_reason)

    receiver_email = _resolve_receiver_email(settings)
    if receiver_email is None:
        reason = "SMTP receiver email is not configured."
        _INQUIRY_LOGGER.warning("Inquiry delivery failed: %s inquiry_id=%s", reason, inquiry.id)
        _set_delivery_status(
            inquiry,
            status="failed",
            reason=reason,
            retry_needed=True,
        )
        inquiry.status = "delivery_failed"
        db.add(inquiry)
        db.commit()
        raise ValueError(reason)

    message = _build_inquiry_email_message(
        payload=payload,
        from_email=settings.smtp_username or "",
        to_email=receiver_email,
    )
    attempt_count = int(delivery.get("attempt_count") or 0) + 1
    _set_delivery_status(
        inquiry,
        status="sending",
        receiver_email=receiver_email,
        attempt_count=attempt_count,
        retry_needed=False,
    )
    db.add(inquiry)
    db.commit()

    try:
        _send_via_smtp(settings=settings, message=message)
    except Exception as exc:  # noqa: BLE001
        reason = sanitize_public_error(str(exc), fallback="Inquiry SMTP delivery failed.")
        _INQUIRY_LOGGER.exception(
            "Failed to send inquiry email notification: inquiry_id=%s attempt=%s error=%s",
            inquiry.id,
            attempt_count,
            exc,
        )
        _set_delivery_status(
            inquiry,
            status="failed",
            reason=reason,
            receiver_email=receiver_email,
            attempt_count=attempt_count,
            retry_needed=True,
        )
        inquiry.status = "delivery_failed"
        db.add(inquiry)
        db.commit()
        raise RuntimeError(reason) from exc

    _INQUIRY_LOGGER.info(
        "Inquiry email notification sent. inquiry_id=%s receiver=%s attempt=%s",
        inquiry.id,
        receiver_email,
        attempt_count,
    )
    _set_delivery_status(
        inquiry,
        status="sent",
        receiver_email=receiver_email,
        attempt_count=attempt_count,
        retry_needed=False,
    )
    inquiry.status = "delivery_sent"
    db.add(inquiry)
    db.commit()


def _build_inquiry_email_message(*, payload: InquiryCreate, from_email: str, to_email: str) -> MIMEMultipart:
    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Reply-To"] = payload.email
    
    # Explicitly encode subject to handle non-ASCII (Korean) characters safely
    from email.header import Header
    subject_text = f"[{payload.inquiry_type.upper()}] 새 문의가 접수되었습니다: {payload.name or '익명'}"
    msg["Subject"] = Header(subject_text, "utf-8").encode()

    body = f"""유형: {payload.inquiry_type}
카테고리: {payload.inquiry_category or '-'}
이름: {payload.name or '-'}
이메일: {payload.email}
연락처: {payload.phone or '-'}
기관명: {payload.institution_name or '-'}
발생위치: {payload.context_location or '-'}

--- 문의내용 ---
{payload.message}
"""
    msg.attach(MIMEText(body, "plain", "utf-8"))
    return msg


def _get_smtp_skip_reason(settings: Settings) -> str | None:
    if not settings.smtp_enabled:
        return _SMTP_DISABLED_REASON
    if not settings.smtp_server:
        return "SMTP_SERVER is empty"
    if settings.smtp_port <= 0:
        return "SMTP_PORT must be greater than zero"
    if not settings.smtp_username:
        return "SMTP_USERNAME is empty"
    if not settings.smtp_password:
        return "SMTP_PASSWORD is empty"
    return None


def _resolve_receiver_email(settings: Settings) -> str | None:
    receiver = (settings.smtp_receiver_email or "").strip()
    if receiver:
        return receiver
    fallback = (settings.smtp_username or "").strip()
    return fallback or None


def _send_via_smtp(*, settings: Settings, message: MIMEMultipart) -> None:
    use_ssl = settings.smtp_port == 465
    smtp_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_cls(settings.smtp_server, settings.smtp_port, timeout=_SMTP_TIMEOUT_SECONDS) as server:
        if not use_ssl:
            server.ehlo()
            if server.has_extn("starttls"):
                server.starttls()
                server.ehlo()
            elif settings.smtp_port == 587:
                _INQUIRY_LOGGER.warning(
                    "SMTP server %s:%s does not advertise STARTTLS on port 587.",
                    settings.smtp_server,
                    settings.smtp_port,
                )
        server.login(settings.smtp_username or "", settings.smtp_password or "")
        server.send_message(message)


def _build_payload_from_inquiry(inquiry: Inquiry) -> InquiryCreate:
    extra = inquiry.extra_fields or {}
    return InquiryCreate.model_validate(
        {
            "inquiry_type": inquiry.inquiry_type,
            "name": inquiry.name,
            "email": inquiry.email,
            "phone": inquiry.phone,
            "subject": inquiry.subject,
            "message": inquiry.message,
            "inquiry_category": inquiry.inquiry_category,
            "institution_name": inquiry.institution_name,
            "institution_type": inquiry.institution_type,
            "source_path": inquiry.source_path,
            "context_location": extra.get("context_location"),
            "metadata": extra.get("metadata"),
        }
    )


def _delivery_state(inquiry: Inquiry) -> dict[str, Any]:
    extra_fields = dict(inquiry.extra_fields or {})
    delivery = extra_fields.get("delivery")
    if isinstance(delivery, dict):
        return dict(delivery)
    return {}


def _set_delivery_status(
    inquiry: Inquiry,
    *,
    status: str,
    reason: str | None = None,
    receiver_email: str | None = None,
    attempt_count: int | None = None,
    async_job_id: str | None = None,
    async_job_status: str | None = None,
    retry_needed: bool | None = None,
) -> None:
    extra_fields = dict(inquiry.extra_fields or {})
    current = _delivery_state(inquiry)
    next_state: dict[str, Any] = {
        **current,
        "status": status,
        "updated_at": _utc_iso(),
    }
    if reason:
        next_state["reason"] = reason[:500]
    if receiver_email:
        next_state["receiver_email"] = receiver_email
    if attempt_count is not None:
        next_state["attempt_count"] = max(0, int(attempt_count))
    if async_job_id:
        next_state["async_job_id"] = async_job_id
    if async_job_status:
        next_state["async_job_status"] = async_job_status
    if retry_needed is not None:
        next_state["retry_needed"] = bool(retry_needed)
    if reason is None and status in {"queued", "sending", "sent", "retrying"}:
        next_state.pop("reason", None)
    if status == "sent":
        next_state["sent_at"] = _utc_iso()
        next_state.pop("reason", None)
        next_state["retry_needed"] = False
    if status in {"failed", "retrying"} and "failed_at" not in next_state:
        next_state["failed_at"] = _utc_iso()

    history = current.get("history")
    history_items = list(history) if isinstance(history, list) else []
    history_event = {
        "status": status,
        "at": _utc_iso(),
    }
    if reason:
        history_event["reason"] = reason[:300]
    if attempt_count is not None:
        history_event["attempt"] = max(0, int(attempt_count))
    history_items.append(history_event)
    next_state["history"] = history_items[-20:]

    extra_fields["delivery"] = next_state
    inquiry.extra_fields = extra_fields


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sync_inquiry_delivery_state_from_job(
    db: Session,
    *,
    inquiry_id: str,
    delivery_status: str,
    inquiry_status: str,
    async_job_id: str,
    async_job_status: str,
    reason: str | None = None,
    retry_needed: bool | None = None,
) -> None:
    inquiry = db.get(Inquiry, inquiry_id)
    if inquiry is None:
        return

    delivery = _delivery_state(inquiry)
    effective_reason = reason
    current_reason = str(delivery.get("reason") or "").strip()
    if (
        current_reason
        and reason
        and reason.strip() == _GENERIC_INQUIRY_DELIVERY_FAILURE
        and delivery_status in {"retrying", "failed"}
    ):
        # Keep the specific SMTP/config failure reason captured at send time.
        effective_reason = current_reason
    _set_delivery_status(
        inquiry,
        status=delivery_status,
        reason=effective_reason,
        async_job_id=async_job_id,
        async_job_status=async_job_status,
        attempt_count=int(delivery.get("attempt_count") or 0),
        retry_needed=retry_needed,
    )
    inquiry.status = inquiry_status
    db.add(inquiry)


def _build_extra_fields(payload: InquiryCreate) -> dict[str, Any]:
    extra_fields: dict[str, Any] = {}
    if payload.metadata:
        extra_fields["metadata"] = payload.metadata
    if payload.context_location:
        extra_fields["context_location"] = payload.context_location
    extra_fields["delivery"] = {
        "status": "received",
        "updated_at": _utc_iso(),
        "attempt_count": 0,
        "retry_needed": False,
        "history": [
            {
                "status": "received",
                "at": _utc_iso(),
            }
        ],
    }
    extra_fields["triage"] = _build_inquiry_triage(payload)
    return extra_fields


def _build_inquiry_triage(payload: InquiryCreate) -> dict[str, Any]:
    risk_flags = _detect_risk_flags(payload)
    category = payload.inquiry_category or _derive_category(payload)
    priority = _resolve_priority(payload=payload, risk_flags=risk_flags)

    prompt_meta: dict[str, str] = {"name": TRIAGE_PROMPT_NAME, "version": "unknown"}
    try:
        asset = get_prompt_registry().get_asset(TRIAGE_PROMPT_NAME)
        prompt_meta = {"name": asset.meta.name, "version": asset.meta.version}
    except PromptRegistryError:
        pass

    return {
        "prompt_asset": prompt_meta,
        "triage_method": "deterministic_v1",
        "category": category,
        "priority": priority,
        "internal_summary": _build_internal_summary(payload=payload, category=category, risk_flags=risk_flags),
        "follow_up_questions": _build_follow_up_questions(payload),
        "risk_flags": risk_flags,
    }


def _derive_category(payload: InquiryCreate) -> str:
    if payload.inquiry_type == "partnership":
        return "partnership_request"
    if payload.inquiry_type == "bug_report":
        return "bug"
    return "other"


def _resolve_priority(*, payload: InquiryCreate, risk_flags: list[str]) -> str:
    if risk_flags:
        return "high"
    if payload.inquiry_type == "bug_report":
        return "high"
    if payload.inquiry_type == "partnership":
        return "medium"
    if payload.inquiry_category == "account_login":
        return "medium"
    return "low"


def _build_internal_summary(*, payload: InquiryCreate, category: str, risk_flags: list[str]) -> str:
    if payload.inquiry_type == "partnership":
        institution_type = payload.institution_type or "organization"
        return (
            f"{payload.institution_name} ({institution_type}) submitted a partnership inquiry "
            f"through {payload.name}. Review scope, deployment context, and follow-up channel."
        )
    if payload.inquiry_type == "bug_report":
        location = payload.context_location or payload.source_path or "unknown location"
        return (
            f"{payload.name} reported a {category} issue around {location}. "
            f"Review reproducibility details and any user-blocking impact."
        )

    subject = payload.subject or category
    summary = f"{payload.name or 'User'} submitted a {category} inquiry about {subject}."
    if risk_flags:
        summary += " The message contains policy-sensitive language and should be reviewed carefully."
    return summary


def _build_follow_up_questions(payload: InquiryCreate) -> list[str]:
    questions: list[str] = []
    if payload.inquiry_type == "partnership":
        questions.append("What student group, program size, or rollout scope is being considered?")
        questions.append("What outcome is the institution hoping to evaluate first?")
    elif payload.inquiry_type == "bug_report":
        questions.append("What exact steps reproduce the issue?")
        questions.append("Which device, browser, or app environment was involved?")
    else:
        questions.append("What exact step or workflow is currently blocked?")
        questions.append("What result were they expecting instead?")
    return questions


def _detect_risk_flags(payload: InquiryCreate) -> list[str]:
    text = " ".join(
        value
        for value in [
            payload.subject or "",
            payload.message,
            payload.context_location or "",
            payload.source_path or "",
        ]
        if value
    )
    risk_flags: list[str] = []
    if _FABRICATION_PATTERN.search(text):
        risk_flags.append("fabrication_request")
    if _GUARANTEE_PATTERN.search(text):
        risk_flags.append("guaranteed_outcome_request")
    if _SENSITIVE_PATTERN.search(payload.message):
        risk_flags.append("sensitive_data_in_message")
    return risk_flags
