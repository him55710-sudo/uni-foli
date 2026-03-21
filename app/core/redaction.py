from __future__ import annotations

import re


SECRET_KEYS = {
    "authorization",
    "password",
    "token",
    "access_token",
    "secret",
    "api_key",
    "object_storage_secret_key",
    "raw_text",
    "cleaned_text",
    "masked_text",
}
EMAIL_PATTERN = re.compile(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
PHONE_PATTERN = re.compile(r"(01[016789]|02|0[3-9][0-9])[- ]?\d{3,4}[- ]?\d{4}")
RRN_PATTERN = re.compile(r"\b\d{6}[- ]?[1-4]\d{6}\b")


def redact_text_for_logs(text: str) -> str:
    if not text:
        return text
    redacted = EMAIL_PATTERN.sub("<EMAIL>", text)
    redacted = PHONE_PATTERN.sub("<PHONE_NUMBER>", redacted)
    redacted = RRN_PATTERN.sub("<KOREAN_RRN>", redacted)
    return redacted


def redact_value(value: object) -> object:
    if isinstance(value, str):
        return redact_text_for_logs(value)
    if isinstance(value, dict):
        return redact_mapping(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    return value


def redact_mapping(mapping: dict[str, object]) -> dict[str, object]:
    redacted: dict[str, object] = {}
    for key, value in mapping.items():
        if key.lower() in SECRET_KEYS:
            redacted[key] = "<REDACTED>"
        else:
            redacted[key] = redact_value(value)
    return redacted
