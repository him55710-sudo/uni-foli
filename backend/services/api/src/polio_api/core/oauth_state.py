from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time


def build_oauth_state(*, provider: str, secret: str) -> str:
    payload = {
        "provider": provider,
        "nonce": secrets.token_urlsafe(18),
        "iat": int(time.time()),
    }
    encoded_payload = _urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(secret.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).digest()
    encoded_signature = _urlsafe_b64encode(signature)
    return f"{encoded_payload}.{encoded_signature}"


def validate_oauth_state(*, state: str, provider: str, secret: str, ttl_seconds: int) -> dict[str, object]:
    try:
        encoded_payload, encoded_signature = state.split(".", 1)
    except ValueError as exc:
        raise ValueError("OAuth state is malformed.") from exc

    expected_signature = hmac.new(
        secret.encode("utf-8"),
        encoded_payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(_urlsafe_b64encode(expected_signature), encoded_signature):
        raise ValueError("OAuth state signature is invalid.")

    try:
        payload = json.loads(_urlsafe_b64decode(encoded_payload).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError("OAuth state payload is invalid.") from exc

    if payload.get("provider") != provider:
        raise ValueError("OAuth state provider mismatch.")

    issued_at = int(payload.get("iat") or 0)
    now = int(time.time())
    if issued_at <= 0 or now - issued_at > ttl_seconds:
        raise ValueError("OAuth state has expired.")

    return payload


def _urlsafe_b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")
