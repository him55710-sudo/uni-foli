from __future__ import annotations

from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from polio_api.api.deps import get_current_user, get_firebase_auth_client
from polio_api.core.config import get_settings
from polio_api.core.oauth_state import build_client_binding, build_oauth_state, validate_oauth_state
from polio_api.core.rate_limit import rate_limit
from polio_api.db.models.user import User
from polio_api.schemas.user import UserProfileRead

router = APIRouter()


class SocialProviderPrepareRequest(BaseModel):
    provider: Literal["kakao", "naver"]


class SocialProviderPrepareResponse(BaseModel):
    provider: Literal["kakao", "naver"]
    state: str
    expires_in: int


class SocialLoginRequest(BaseModel):
    provider: Literal["kakao", "naver"]
    code: str = Field(min_length=1, max_length=2048)
    state: str = Field(min_length=16, max_length=1024)


class SocialLoginResponse(BaseModel):
    firebase_custom_token: str


@router.post("/firebase/exchange", response_model=UserProfileRead)
def firebase_exchange(current_user: User = Depends(get_current_user)) -> UserProfileRead:
    return UserProfileRead.model_validate(current_user)


@router.post(
    "/social/prepare",
    response_model=SocialProviderPrepareResponse,
    dependencies=[Depends(rate_limit(bucket="social_prepare", limit=20, window_seconds=300))],
)
def prepare_social_login(
    payload: SocialProviderPrepareRequest,
    request: Request,
) -> SocialProviderPrepareResponse:
    settings = get_settings()
    _ensure_social_login_enabled(settings)
    state_secret = settings.auth_social_state_secret
    if not state_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Social login is not configured.",
        )
    client_binding = build_client_binding(
        request.headers.get("user-agent"),
        request.client.host if request.client else None,
    )
    state = build_oauth_state(
        provider=payload.provider,
        secret=state_secret,
        client_binding=client_binding,
    )
    return SocialProviderPrepareResponse(
        provider=payload.provider,
        state=state,
        expires_in=settings.auth_social_state_ttl_seconds,
    )


@router.post(
    "/social",
    response_model=SocialLoginResponse,
    dependencies=[Depends(rate_limit(bucket="social_login", limit=10, window_seconds=300))],
)
async def social_login(payload: SocialLoginRequest, request: Request) -> SocialLoginResponse:
    settings = get_settings()
    _ensure_social_login_enabled(settings)
    _require_provider_config(settings, payload.provider)

    try:
        validate_oauth_state(
            state=payload.state,
            provider=payload.provider,
            secret=settings.auth_social_state_secret or "",
            ttl_seconds=settings.auth_social_state_ttl_seconds,
            client_binding=build_client_binding(
                request.headers.get("user-agent"),
                request.client.host if request.client else None,
            ),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state.",
        ) from exc

    timeout = httpx.Timeout(10.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        if payload.provider == "kakao":
            uid, email, name = await _exchange_kakao_code(client, settings, payload.code)
        else:
            uid, email, name = await _exchange_naver_code(client, settings, payload.code)

    auth_client = get_firebase_auth_client()
    try:
        try:
            firebase_user = auth_client.get_user_by_email(email) if email else auth_client.get_user(uid)
        except auth_client.UserNotFoundError:
            firebase_user = auth_client.create_user(
                uid=uid,
                email=email,
                display_name=name,
            )

        custom_token = auth_client.create_custom_token(firebase_user.uid).decode("utf-8")
        return SocialLoginResponse(firebase_custom_token=custom_token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Social login could not be completed.",
        ) from exc


def _ensure_social_login_enabled(settings) -> None:
    if not settings.auth_social_login_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Social login is disabled.",
        )


def _require_provider_config(settings, provider: Literal["kakao", "naver"]) -> None:
    if provider == "kakao":
        if not settings.kakao_client_id or settings.kakao_client_id.startswith("DUMMY_"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Kakao login is not configured.",
            )
        return

    if not settings.naver_client_id or settings.naver_client_id.startswith("DUMMY_"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Naver login is not configured.",
        )
    if not settings.naver_client_secret or settings.naver_client_secret.startswith("DUMMY_"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Naver login is not configured.",
        )


async def _exchange_kakao_code(client: httpx.AsyncClient, settings, code: str) -> tuple[str, str | None, str | None]:
    token_response = await client.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": settings.kakao_client_id,
            "redirect_uri": settings.kakao_redirect_uri,
            "code": code,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if token_response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Kakao code exchange failed.")

    access_token = str(token_response.json().get("access_token") or "").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Kakao access token missing.")

    user_response = await client.get(
        "https://kapi.kakao.com/v2/user/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if user_response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Kakao user lookup failed.")

    user_info = user_response.json()
    kakao_id = str(user_info.get("id") or "").strip()
    if not kakao_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Kakao user id missing.")
    email = user_info.get("kakao_account", {}).get("email")
    name = user_info.get("properties", {}).get("nickname", "Kakao User")
    return f"kakao:{kakao_id}", email, name


async def _exchange_naver_code(client: httpx.AsyncClient, settings, code: str) -> tuple[str, str | None, str | None]:
    token_response = await client.get(
        "https://nid.naver.com/oauth2.0/token",
        params={
            "grant_type": "authorization_code",
            "client_id": settings.naver_client_id,
            "client_secret": settings.naver_client_secret,
            "code": code,
        },
    )
    if token_response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Naver code exchange failed.")

    access_token = str(token_response.json().get("access_token") or "").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Naver access token missing.")

    user_response = await client.get(
        "https://openapi.naver.com/v1/nid/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if user_response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Naver user lookup failed.")

    profile = user_response.json().get("response", {})
    naver_id = str(profile.get("id") or "").strip()
    if not naver_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Naver user id missing.")
    email = profile.get("email")
    name = profile.get("name", "Naver User")
    return f"naver:{naver_id}", email, name
