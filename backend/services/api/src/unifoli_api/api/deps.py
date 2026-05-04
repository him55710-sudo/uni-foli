import base64
from collections.abc import Generator
from dataclasses import dataclass
from functools import lru_cache
import json
import os
from pathlib import Path
import re
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from unifoli_api.core.database import SessionLocal
from unifoli_api.db.models.user import User
from unifoli_shared.paths import resolve_runtime_path

security = HTTPBearer()
LOCAL_DEV_JWT_SECRET = "local-dev-secret-please-change-1234567890"


def _get_auth_bootstrap_settings():
    from unifoli_api.core.config import get_settings

    return get_settings()


def _resolve_firebase_project_id(certificate_payload: dict[str, Any] | None = None) -> str | None:
    if certificate_payload:
        project_id = str(certificate_payload.get("project_id") or "").strip()
        if project_id:
            return project_id

    for env_name in ("FIREBASE_PROJECT_ID", "GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT"):
        value = os.getenv(env_name, "").strip()
        if value:
            return value

    settings = _get_auth_bootstrap_settings()
    configured_value = str(getattr(settings, "firebase_project_id", "") or "").strip()
    if configured_value:
        return configured_value

    return None


def _resolve_google_application_credentials_path() -> str | None:
    raw_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not raw_path:
        settings = _get_auth_bootstrap_settings()
        raw_path = str(getattr(settings, "google_application_credentials", "") or "").strip()
    if not raw_path:
        return None

    return str(resolve_runtime_path(raw_path).expanduser())


def _strip_matching_env_quotes(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {'"', "'"}:
        return stripped[1:-1].strip()
    return stripped


def _remove_escaped_json_formatting_newlines(value: str) -> str:
    normalized = value.replace("\\r\\n", "\\n")
    normalized = re.sub(r"^\s*\\n\s*", "", normalized)
    normalized = re.sub(r"(?:\\n\s*)+$", "", normalized)
    normalized = re.sub(r'\\n\s*(?="[^"\\]*(?:\\.[^"\\]*)*"\s*:)', "", normalized)
    normalized = re.sub(r"\\n\s*(?=})", "", normalized)
    return normalized


def _load_firebase_service_account_payload(raw_value: str) -> dict[str, Any]:
    """Parse Firebase credentials from common Vercel env var encodings."""

    candidates: list[str] = []
    stripped = raw_value.strip()
    unquoted = _strip_matching_env_quotes(stripped)
    candidates.extend(
        candidate
        for candidate in (
            stripped,
            unquoted,
            _remove_escaped_json_formatting_newlines(unquoted),
        )
        if candidate
    )

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            payload: Any = json.loads(candidate)
            if isinstance(payload, str):
                payload = json.loads(_remove_escaped_json_formatting_newlines(_strip_matching_env_quotes(payload)))
            if not isinstance(payload, dict):
                raise ValueError("Firebase service account payload must be a JSON object.")
            private_key = payload.get("private_key")
            if isinstance(private_key, str) and "\\n" in private_key:
                payload = {**payload, "private_key": private_key.replace("\\n", "\n")}
            return payload
        except Exception as exc:  # noqa: BLE001
            last_error = exc

    raise ValueError("Firebase service account JSON could not be parsed.") from last_error


@lru_cache(maxsize=1)
def get_firebase_auth_client():
    """Initializes the Firebase Admin SDK client once."""
    try:
        import firebase_admin
        from firebase_admin import auth
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "firebase-admin is not installed. "
                "Run setup-local again to install backend dependencies."
            ),
        ) from exc

    if not firebase_admin._apps:
        settings = _get_auth_bootstrap_settings()
        inline_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip() or str(
            getattr(settings, "firebase_service_account_json", "") or ""
        ).strip()
        inline_json_b64 = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON_BASE64", "").strip() or str(
            getattr(settings, "firebase_service_account_json_base64", "") or ""
        ).strip()
        credential = None
        project_id = None

        if inline_json or inline_json_b64:
            try:
                if inline_json_b64:
                    inline_json = base64.b64decode(inline_json_b64).decode("utf-8")
                certificate_payload = _load_firebase_service_account_payload(inline_json)
                project_id = _resolve_firebase_project_id(certificate_payload)
                credential = firebase_admin.credentials.Certificate(certificate_payload)
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Firebase service account configuration is invalid.",
                ) from exc
        else:
            credentials_path = _resolve_google_application_credentials_path()
            if credentials_path:
                credential_path = Path(credentials_path)
                if credential_path.exists():
                    try:
                        credential = firebase_admin.credentials.Certificate(str(credential_path))
                    except Exception as exc:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Firebase service account file is invalid.",
                        ) from exc
            project_id = _resolve_firebase_project_id()

        init_kwargs: dict[str, Any] = {}
        if credential is not None:
            init_kwargs["credential"] = credential
        if project_id:
            init_kwargs["options"] = {"projectId": project_id}

        if init_kwargs:
            firebase_admin.initialize_app(**init_kwargs)
        else:
            # Fall back to ADC when no explicit credential or project id is configured.
            firebase_admin.initialize_app()

    return auth


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@dataclass(frozen=True)
class AuthClaims:
    subject: str
    email: str | None
    name: str | None
    raw: dict[str, Any]


def _get_jwt_key(settings) -> str | None:
    if settings.auth_jwt_public_key:
        return settings.auth_jwt_public_key
    if settings.auth_jwt_secret:
        return settings.auth_jwt_secret
    return None


def _decode_jwt_claims(token: str, settings) -> AuthClaims:
    jwt_key = _get_jwt_key(settings)
    if jwt_key is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT verification is not configured for this environment.",
        )

    options = {
        "require": ["sub"],
        "verify_aud": bool(settings.auth_jwt_audience),
        "verify_iss": bool(settings.auth_jwt_issuer),
    }

    try:
        payload = jwt.decode(
            token,
            jwt_key,
            algorithms=[settings.auth_jwt_algorithm],
            audience=settings.auth_jwt_audience if settings.auth_jwt_audience else None,
            issuer=settings.auth_jwt_issuer if settings.auth_jwt_issuer else None,
            options=options,
            leeway=settings.auth_token_leeway_seconds,
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    subject = str(payload.get("sub") or payload.get("uid") or "").strip()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthClaims(
        subject=subject,
        email=payload.get("email"),
        name=payload.get("name") or payload.get("display_name"),
        raw=dict(payload),
    )


def _decode_firebase_claims(token: str) -> AuthClaims:
    auth_client = get_firebase_auth_client()
    try:
        decoded_token = auth_client.verify_id_token(token)
    except Exception as exc:
        import sys
        print(f"FIREBASE AUTH ERROR: {exc}", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    subject = str(decoded_token.get("uid") or "").strip()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing uid.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthClaims(
        subject=subject,
        email=decoded_token.get("email"),
        name=decoded_token.get("name"),
        raw=dict(decoded_token),
    )


def _sync_user_from_claims(db: Session, claims: AuthClaims) -> User:
    user = db.query(User).filter(User.firebase_uid == claims.subject).first()
    if user is None and claims.email:
        user = db.query(User).filter(User.email == claims.email).first()

    if user is None:
        user = User(
            firebase_uid=claims.subject,
            email=claims.email,
            name=claims.name,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    changed = False
    if user.firebase_uid != claims.subject:
        user.firebase_uid = claims.subject
        changed = True
    if user.email != claims.email:
        user.email = claims.email
        changed = True
    if user.name != claims.name:
        user.name = claims.name
        changed = True

    if changed:
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _get_or_create_local_dev_user(db: Session) -> User:
    claims = AuthClaims(
        subject="local:test-user-id",
        email="test@example.com",
        name="Local Test User",
        raw={"sub": "local:test-user-id", "email": "test@example.com", "name": "Local Test User"},
    )
    return _sync_user_from_claims(db, claims)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db),
) -> User:
    from unifoli_api.core.config import get_settings
    settings = get_settings()
    local_bypass_enabled = settings.auth_allow_local_dev_bypass

    if not credentials:
        if local_bypass_enabled:
            user = _get_or_create_local_dev_user(db)
            request.state.current_user_id = user.id
            request.state.tenant_user_id = user.id
            request.state.auth_claims = {"sub": user.firebase_uid, "email": user.email, "name": user.name}
            return user

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        try:
            claims = _decode_jwt_claims(token, settings)
        except HTTPException:
            if not settings.auth_firebase_fallback_enabled:
                raise
            claims = _decode_firebase_claims(token)
    except HTTPException as exc:
        if settings.auth_allow_local_dev_bypass:
            user = _get_or_create_local_dev_user(db)
            request.state.current_user_id = user.id
            request.state.tenant_user_id = user.id
            request.state.auth_claims = {"sub": user.firebase_uid, "email": user.email, "name": user.name}
            return user
        raise

    user = _sync_user_from_claims(db, claims)
    request.state.current_user_id = user.id
    request.state.tenant_user_id = user.id
    request.state.auth_claims = claims.raw
    return user

def _claims_indicate_admin(claims: dict[str, Any] | None) -> bool:
    if not isinstance(claims, dict):
        return False
    if claims.get("admin") is True or claims.get("is_admin") is True:
        return True
    roles = claims.get("roles") or claims.get("role")
    if isinstance(roles, str):
        return roles.strip().lower() == "admin"
    if isinstance(roles, list):
        return any(str(role).strip().lower() == "admin" for role in roles)
    return False


def get_current_admin(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> User:
    from unifoli_api.core.config import get_settings

    settings = get_settings()
    configured_admin_emails = {email.strip().lower() for email in settings.admin_emails if email.strip()}
    current_email = (current_user.email or "").strip().lower()
    auth_claims = getattr(request.state, "auth_claims", None)

    if current_email not in configured_admin_emails and not _claims_indicate_admin(auth_claims):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 페이지에 접근할 권한이 없습니다. 관리자만 이용 가능합니다.",
        )
    return current_user
