from __future__ import annotations

from polio_api.core.config import Settings
from polio_api.schemas.inquiry import InquiryCreate
from polio_api.services import inquiry_service


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


def _build_payload() -> InquiryCreate:
    return InquiryCreate(
        inquiry_type="one_to_one",
        name="테스터",
        email="tester@example.com",
        subject="로그인 문의",
        message="로그인이 되지 않아 문의드립니다. 확인 부탁드립니다.",
        inquiry_category="account_login",
    )


def _build_settings(**overrides: object) -> Settings:
    defaults = {
        "smtp_enabled": True,
        "smtp_server": "smtp.naver.com",
        "smtp_port": 587,
        "smtp_username": "sender@naver.com",
        "smtp_password": "app-password",
        "smtp_receiver_email": "mongben@naver.com",
    }
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)


def test_inquiry_email_notification_sends_with_configured_receiver(monkeypatch) -> None:
    _FakeSMTP.instances.clear()
    monkeypatch.setattr(inquiry_service, "get_settings", lambda: _build_settings())
    monkeypatch.setattr(inquiry_service.smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(inquiry_service.smtplib, "SMTP_SSL", _FakeSMTP)

    inquiry_service._send_email_notification_safe(_build_payload())

    assert len(_FakeSMTP.instances) == 1
    smtp = _FakeSMTP.instances[0]
    assert smtp.host == "smtp.naver.com"
    assert smtp.port == 587
    assert "starttls" in smtp.events
    assert ("login", "sender@naver.com", "app-password") in smtp.events
    assert len(smtp.sent_messages) == 1
    assert smtp.sent_messages[0]["To"] == "mongben@naver.com"
    assert smtp.sent_messages[0]["Reply-To"] == "tester@example.com"


def test_inquiry_email_notification_skips_with_clear_reason(monkeypatch, caplog) -> None:
    _FakeSMTP.instances.clear()

    def _should_not_send(*args, **kwargs):  # noqa: ANN001, ANN202
        raise AssertionError("SMTP client should not be called when SMTP is disabled.")

    monkeypatch.setattr(inquiry_service, "get_settings", lambda: _build_settings(smtp_enabled=False))
    monkeypatch.setattr(inquiry_service.smtplib, "SMTP", _should_not_send)
    monkeypatch.setattr(inquiry_service.smtplib, "SMTP_SSL", _should_not_send)

    with caplog.at_level("WARNING", logger="polio.api.inquiries"):
        inquiry_service._send_email_notification_safe(_build_payload())

    assert "SMTP_ENABLED=false" in caplog.text


def test_inquiry_email_notification_falls_back_to_sender_when_receiver_missing(monkeypatch) -> None:
    _FakeSMTP.instances.clear()
    monkeypatch.setattr(
        inquiry_service,
        "get_settings",
        lambda: _build_settings(smtp_receiver_email="   "),
    )
    monkeypatch.setattr(inquiry_service.smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(inquiry_service.smtplib, "SMTP_SSL", _FakeSMTP)

    inquiry_service._send_email_notification_safe(_build_payload())

    assert len(_FakeSMTP.instances) == 1
    smtp = _FakeSMTP.instances[0]
    assert len(smtp.sent_messages) == 1
    assert smtp.sent_messages[0]["To"] == "sender@naver.com"
