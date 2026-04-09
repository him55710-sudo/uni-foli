from __future__ import annotations

import smtplib

import pytest
from sqlalchemy import select

from polio_api.core.config import get_settings
from polio_api.core.database import SessionLocal
from polio_api.db.models.inquiry import Inquiry
from polio_api.schemas.inquiry import InquiryCreate
from polio_api.services import inquiry_service
from polio_api.services import async_job_service
from polio_api.services.async_job_service import get_latest_job_for_resource, process_async_job


class _FakeSMTP:
    instances: list["_FakeSMTP"] = []

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.events: list[str | tuple[str, str, str] | tuple[str, str]] = []
        self.sent_messages = []
        self.__class__.instances.append(self)

    def __enter__(self) -> "_FakeSMTP":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        return False

    def ehlo(self) -> None:
        self.events.append("ehlo")

    def has_extn(self, name: str) -> bool:
        return name.lower() == "starttls"

    def starttls(self) -> None:
        self.events.append("starttls")

    def login(self, username: str, password: str) -> None:
        self.events.append(("login", username, password))

    def send_message(self, message) -> None:  # noqa: ANN001
        self.sent_messages.append(message)
        self.events.append(("send", message["To"]))


def _payload() -> InquiryCreate:
    return InquiryCreate(
        inquiry_type="one_to_one",
        name="테스터",
        email="tester@example.com",
        subject="로그인 문의",
        message="로그인이 되지 않아 문의드립니다. 확인 부탁드립니다.",
        inquiry_category="account_login",
        context_location="/app/login",
    )


def _apply_settings(**overrides: object):
    settings = get_settings()
    originals = {key: getattr(settings, key) for key in overrides}
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings, originals


def _restore_settings(settings, originals) -> None:  # noqa: ANN001
    for key, value in originals.items():
        setattr(settings, key, value)


def _create_inquiry_and_job():
    with SessionLocal() as db:
        inquiry = inquiry_service.create_inquiry(db, _payload())
        job = get_latest_job_for_resource(db, resource_type="inquiry", resource_id=inquiry.id)
        assert job is not None
        return inquiry.id, job.id


def _load_inquiry(inquiry_id: str) -> Inquiry:
    with SessionLocal() as db:
        inquiry = db.scalar(select(Inquiry).where(Inquiry.id == inquiry_id))
        assert inquiry is not None
        return inquiry


def _process_job(job_id: str):
    with SessionLocal() as db:
        processed = process_async_job(db, job_id)
        assert processed is not None
        return processed


def test_inquiry_email_delivery_skipped_when_smtp_disabled() -> None:
    settings, originals = _apply_settings(
        async_jobs_inline_dispatch=False,
        async_job_retry_delay_seconds=0,
        async_job_max_retries=1,
        smtp_enabled=False,
        smtp_server="smtp.naver.com",
        smtp_port=587,
        smtp_username="sender@naver.com",
        smtp_password="app-password",
        smtp_receiver_email="mongben@naver.com",
    )
    try:
        inquiry_id, job_id = _create_inquiry_and_job()
        processed = _process_job(job_id)
        inquiry = _load_inquiry(inquiry_id)
        delivery = inquiry.extra_fields["delivery"]

        assert processed.status == "succeeded"
        assert inquiry.status == "delivery_skipped"
        assert delivery["status"] == "skipped"
        assert delivery["reason"] == "SMTP_ENABLED=false"
        assert delivery["retry_needed"] is False
    finally:
        _restore_settings(settings, originals)


def test_inquiry_email_delivery_missing_credentials_enters_retry_then_failed() -> None:
    settings, originals = _apply_settings(
        async_jobs_inline_dispatch=False,
        async_job_retry_delay_seconds=0,
        async_job_max_retries=1,
        smtp_enabled=True,
        smtp_server="smtp.naver.com",
        smtp_port=587,
        smtp_username=None,
        smtp_password=None,
        smtp_receiver_email="mongben@naver.com",
    )
    try:
        inquiry_id, job_id = _create_inquiry_and_job()

        first = _process_job(job_id)
        inquiry_after_first = _load_inquiry(inquiry_id)
        first_delivery = inquiry_after_first.extra_fields["delivery"]

        assert first.status == "retrying"
        assert inquiry_after_first.status == "delivery_retrying"
        assert first_delivery["status"] == "retrying"
        assert first_delivery["retry_needed"] is True
        assert "SMTP_USERNAME is empty" in first_delivery.get("reason", "")

        second = _process_job(job_id)
        inquiry_after_second = _load_inquiry(inquiry_id)
        second_delivery = inquiry_after_second.extra_fields["delivery"]

        assert second.status == "failed"
        assert inquiry_after_second.status == "delivery_failed"
        assert second_delivery["status"] == "failed"
        assert second_delivery["retry_needed"] is True
        assert "SMTP_USERNAME is empty" in second_delivery.get("reason", "")
    finally:
        _restore_settings(settings, originals)


def test_inquiry_email_delivery_success_with_naver_receiver(monkeypatch) -> None:
    _FakeSMTP.instances.clear()
    settings, originals = _apply_settings(
        async_jobs_inline_dispatch=False,
        async_job_retry_delay_seconds=0,
        async_job_max_retries=1,
        smtp_enabled=True,
        smtp_server="smtp.naver.com",
        smtp_port=587,
        smtp_username="sender@naver.com",
        smtp_password="app-password",
        smtp_receiver_email="mongben@naver.com",
    )
    monkeypatch.setattr(inquiry_service.smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(inquiry_service.smtplib, "SMTP_SSL", _FakeSMTP)

    try:
        inquiry_id, job_id = _create_inquiry_and_job()
        processed = _process_job(job_id)
        inquiry = _load_inquiry(inquiry_id)
        delivery = inquiry.extra_fields["delivery"]

        assert processed.status == "succeeded"
        assert inquiry.status == "delivery_sent"
        assert delivery["status"] == "sent"
        assert delivery["retry_needed"] is False
        assert delivery["attempt_count"] == 1

        assert len(_FakeSMTP.instances) == 1
        smtp = _FakeSMTP.instances[0]
        assert smtp.host == "smtp.naver.com"
        assert smtp.port == 587
        assert "starttls" in smtp.events
        assert ("login", "sender@naver.com", "app-password") in smtp.events
        assert len(smtp.sent_messages) == 1
        sent_message = smtp.sent_messages[0]
        assert sent_message["To"] == "mongben@naver.com"
        assert sent_message["Reply-To"] == "tester@example.com"
        assert "=?utf-8?" in str(sent_message["Subject"]).lower()
    finally:
        _restore_settings(settings, originals)


def test_inquiry_email_delivery_failure_preserves_record(monkeypatch) -> None:
    settings, originals = _apply_settings(
        async_jobs_inline_dispatch=False,
        async_job_retry_delay_seconds=0,
        async_job_max_retries=0,
        smtp_enabled=True,
        smtp_server="smtp.naver.com",
        smtp_port=587,
        smtp_username="sender@naver.com",
        smtp_password="app-password",
        smtp_receiver_email="mongben@naver.com",
    )
    monkeypatch.setattr(
        inquiry_service,
        "_send_via_smtp",
        lambda **kwargs: (_ for _ in ()).throw(smtplib.SMTPException("auth failed")),
    )

    try:
        inquiry_id, job_id = _create_inquiry_and_job()
        processed = _process_job(job_id)
        inquiry = _load_inquiry(inquiry_id)
        delivery = inquiry.extra_fields["delivery"]

        assert processed.status == "failed"
        assert inquiry.status == "delivery_failed"
        assert delivery["status"] == "failed"
        assert delivery["retry_needed"] is True
        assert inquiry.message == _payload().message
    finally:
        _restore_settings(settings, originals)


def test_inquiry_email_delivery_retry_path_succeeds_after_transient_error(monkeypatch) -> None:
    settings, originals = _apply_settings(
        async_jobs_inline_dispatch=False,
        async_job_retry_delay_seconds=0,
        async_job_max_retries=1,
        smtp_enabled=True,
        smtp_server="smtp.naver.com",
        smtp_port=587,
        smtp_username="sender@naver.com",
        smtp_password="app-password",
        smtp_receiver_email="mongben@naver.com",
    )
    attempts = {"count": 0}

    def flaky_send(**kwargs) -> None:  # noqa: ANN003
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("temporary timeout")

    monkeypatch.setattr(inquiry_service, "_send_via_smtp", flaky_send)

    try:
        inquiry_id, job_id = _create_inquiry_and_job()

        first = _process_job(job_id)
        inquiry_after_first = _load_inquiry(inquiry_id)
        assert first.status == "retrying"
        assert inquiry_after_first.status == "delivery_retrying"
        assert inquiry_after_first.extra_fields["delivery"]["status"] == "retrying"

        second = _process_job(job_id)
        inquiry_after_second = _load_inquiry(inquiry_id)
        assert second.status == "succeeded"
        assert inquiry_after_second.status == "delivery_sent"
        assert inquiry_after_second.extra_fields["delivery"]["status"] == "sent"
        assert inquiry_after_second.extra_fields["delivery"]["attempt_count"] == 2
    finally:
        _restore_settings(settings, originals)


def test_inquiry_record_persists_even_when_queue_creation_fails(monkeypatch) -> None:
    settings, originals = _apply_settings(
        async_jobs_inline_dispatch=False,
        smtp_enabled=True,
        smtp_server="smtp.naver.com",
        smtp_port=587,
        smtp_username="sender@naver.com",
        smtp_password="app-password",
        smtp_receiver_email="mongben@naver.com",
    )
    monkeypatch.setattr(
        async_job_service,
        "create_async_job",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("queue offline")),
    )

    try:
        with SessionLocal() as db:
            inquiry = inquiry_service.create_inquiry(db, _payload())
            delivery = inquiry.extra_fields["delivery"]

            assert inquiry.status == "delivery_failed"
            assert delivery["status"] == "failed"
            assert delivery["retry_needed"] is True
            assert delivery["reason"]
            assert db.scalar(select(Inquiry).where(Inquiry.id == inquiry.id)) is not None
    finally:
        _restore_settings(settings, originals)
