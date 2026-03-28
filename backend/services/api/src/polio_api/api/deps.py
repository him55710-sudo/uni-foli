from collections.abc import Generator
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from polio_api.core.database import SessionLocal
from polio_api.db.models.user import User

security = HTTPBearer()
LOCAL_DEV_JWT_SECRET = "local-dev-secret-please-change-1234567890"


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
        # Defaults to ADC or GOOGLE_APPLICATION_CREDENTIALS path
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
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
    from polio_api.core.config import get_settings
    settings = get_settings()
    local_bypass_enabled = settings.app_env == "local" and settings.auth_allow_local_dev_bypass

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
    except HTTPException:
        raise

    user = _sync_user_from_claims(db, claims)
    request.state.current_user_id = user.id
    request.state.tenant_user_id = user.id
    request.state.auth_claims = claims.raw
    return user
