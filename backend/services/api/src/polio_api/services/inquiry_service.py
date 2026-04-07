from __future__ import annotations

import logging
import re
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from sqlalchemy.orm import Session

from polio_api.core.config import Settings, get_settings
from polio_api.db.models.inquiry import Inquiry
from polio_api.schemas.inquiry import InquiryCreate
from polio_api.services.prompt_registry import PromptRegistryError, get_prompt_registry

TRIAGE_PROMPT_NAME = "inquiry-support.contact-triage"
_INQUIRY_LOGGER = logging.getLogger("polio.api.inquiries")
_SMTP_TIMEOUT_SECONDS = 20.0
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
    
    # Notify via email asynchronously so it doesn't block the API response
    threading.Thread(target=_send_email_notification_safe, args=(payload,), daemon=True).start()
    
    return inquiry


def _send_email_notification_safe(payload: InquiryCreate) -> None:
    settings = get_settings()
    smtp_skip_reason = _get_smtp_skip_reason(settings)
    if smtp_skip_reason is not None:
        _INQUIRY_LOGGER.warning("Skipping inquiry email notification: %s", smtp_skip_reason)
        return

    receiver_email = _resolve_receiver_email(settings)
    if receiver_email is None:
        _INQUIRY_LOGGER.warning("Skipping inquiry email notification: SMTP receiver email is not configured.")
        return

    message = _build_inquiry_email_message(
        payload=payload,
        from_email=settings.smtp_username or "",
        to_email=receiver_email,
    )

    try:
        _send_via_smtp(settings=settings, message=message)
        _INQUIRY_LOGGER.info(
            "Inquiry email notification sent to %s for inquiry_type=%s",
            receiver_email,
            payload.inquiry_type,
        )
    except Exception as e:
        _INQUIRY_LOGGER.exception("Failed to send inquiry email notification: %s", e)


def _build_inquiry_email_message(*, payload: InquiryCreate, from_email: str, to_email: str) -> MIMEMultipart:
    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Reply-To"] = payload.email
    msg["Subject"] = f"[{payload.inquiry_type.upper()}] 새 문의가 접수되었습니다: {payload.name or '익명'}"

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
        return "SMTP_ENABLED=false"
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


def _build_extra_fields(payload: InquiryCreate) -> dict[str, Any]:
    extra_fields: dict[str, Any] = {}
    if payload.metadata:
        extra_fields["metadata"] = payload.metadata
    if payload.context_location:
        extra_fields["context_location"] = payload.context_location
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
