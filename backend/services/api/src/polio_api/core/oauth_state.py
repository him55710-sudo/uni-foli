from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from threading import Lock
import time

_CONSUMED_NONCES: dict[str, int] = {}
_NONCE_LOCK = Lock()


def build_client_binding(user_agent: str | None, client_host: str | None) -> str:
    normalized_user_agent = " ".join((user_agent or "").split()).strip().lower()[:200]
    normalized_host = (client_host or "").strip().lower()
    material = f"{normalized_user_agent}|{normalized_host}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def build_oauth_state(*, provider: str, secret: str, client_binding: str | None = None) -> str:
    payload = {
        "provider": provider,
        "nonce": secrets.token_urlsafe(18),
        "iat": int(time.time()),
        "cb": client_binding or "",
    }
    encoded_payload = _urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(secret.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).digest()
    encoded_signature = _urlsafe_b64encode(signature)
    return f"{encoded_payload}.{encoded_signature}"


def validate_oauth_state(
    *,
    state: str,
    provider: str,
    secret: str,
    ttl_seconds: int,
    client_binding: str | None = None,
) -> dict[str, object]:
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
    if payload.get("cb") != (client_binding or ""):
        raise ValueError("OAuth state client binding mismatch.")

    nonce = str(payload.get("nonce") or "").strip()
    if not nonce:
        raise ValueError("OAuth state nonce is missing.")
    _consume_nonce_once(nonce=nonce, expires_at=issued_at + ttl_seconds, now=now)

    return payload


def _consume_nonce_once(*, nonce: str, expires_at: int, now: int) -> None:
    with _NONCE_LOCK:
        expired_nonces = [item for item, expiry in _CONSUMED_NONCES.items() if expiry <= now]
        for item in expired_nonces:
            _CONSUMED_NONCES.pop(item, None)

        existing_expiry = _CONSUMED_NONCES.get(nonce)
        if existing_expiry is not None and existing_expiry > now:
            raise ValueError("OAuth state has already been used.")

        _CONSUMED_NONCES[nonce] = expires_at


def _urlsafe_b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")
