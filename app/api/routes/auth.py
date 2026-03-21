from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_principal, get_db_session
from app.schemas.auth import AuthMeRead, LoginRequest, LoginResponse
from services.admissions.auth_service import auth_service


router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, session: Session = Depends(get_db_session)) -> LoginResponse:
    account = auth_service.authenticate(session, email=payload.email, password=payload.password)
    if account is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    token, _ = auth_service.create_session_token(session, account=account)
    session.commit()
    return LoginResponse(
        access_token=token,
        account_id=account.id,
        tenant_id=account.tenant_id,
        role_slug=account.role.slug,
        email=account.email,
    )


@router.get("/me", response_model=AuthMeRead)
def me(principal=Depends(get_current_principal)) -> AuthMeRead:
    return AuthMeRead(
        account_id=principal.account_id,
        tenant_id=principal.tenant_id,
        role_slug=principal.role_slug,
        email=principal.email,
        full_name=principal.full_name,
        is_admin=principal.is_admin,
        global_access=principal.global_access,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: Session = Depends(get_db_session),
) -> None:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
    auth_service.revoke_session(session, raw_token=authorization.split(" ", 1)[1].strip())
    session.commit()
