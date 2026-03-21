from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from db.session import get_session_factory
from services.admissions.access_control_service import access_control_service
from services.admissions.auth_service import AuthenticatedPrincipal, auth_service


def get_db_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def get_owner_key(x_owner_key: str | None = Header(default=None, alias="X-Owner-Key")) -> str:
    return x_owner_key or get_settings().default_owner_key


def get_current_principal(
    session: Session = Depends(get_db_session),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> AuthenticatedPrincipal:
    settings = get_settings()
    if not settings.auth_enabled:
        account = auth_service.get_account_by_email(session, settings.auth_default_admin_email)
        if account is None or account.role is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication bootstrap is unavailable.")
        return AuthenticatedPrincipal(
            account_id=account.id,
            tenant_id=account.tenant_id,
            role_slug=account.role.slug,
            email=account.email,
            full_name=account.full_name,
            is_admin=account.role.is_admin,
            global_access=account.role.global_access,
        )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
    raw_token = authorization.split(" ", 1)[1].strip()
    principal = auth_service.resolve_principal(session, raw_token=raw_token)
    if principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session.")
    return principal


def require_authenticated_principal(
    session: Session = Depends(get_db_session),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> AuthenticatedPrincipal:
    return get_current_principal(session=session, authorization=authorization)


def require_admin_principal(
    session: Session = Depends(get_db_session),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> AuthenticatedPrincipal:
    principal = get_current_principal(session=session, authorization=authorization)
    try:
        access_control_service.require_admin(principal)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return principal
