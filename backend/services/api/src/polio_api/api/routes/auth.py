from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import httpx
from firebase_admin import auth
from typing import Literal

from polio_api.core.config import get_settings

router = APIRouter()

class SocialLoginRequest(BaseModel):
    provider: Literal["kakao", "naver"]
    code: str

class SocialLoginResponse(BaseModel):
    firebase_custom_token: str

@router.post("/social", response_model=SocialLoginResponse)
async def social_login(payload: SocialLoginRequest):
    settings = get_settings()
    
    if payload.provider == "kakao":
        # 1. Get Kakao Access Token
        async with httpx.AsyncClient() as client:
            token_res = await client.post(
                "https://kauth.kakao.com/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.kakao_client_id,
                    "redirect_uri": settings.kakao_redirect_uri,
                    "code": payload.code,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            if token_res.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to get Kakao token")
            
            access_token = token_res.json().get("access_token")
            
            # 2. Get User Info
            user_res = await client.get(
                "https://kapi.kakao.com/v2/user/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            user_info = user_res.json()
            kakao_id = str(user_info.get("id"))
            email = user_info.get("kakao_account", {}).get("email")
            name = user_info.get("properties", {}).get("nickname", "Kakao User")
            
            uid = f"kakao:{kakao_id}"

    elif payload.provider == "naver":
        # 1. Get Naver Access Token
        async with httpx.AsyncClient() as client:
            token_res = await client.get(
                "https://nid.naver.com/oauth2.0/token",
                params={
                    "grant_type": "authorization_code",
                    "client_id": settings.naver_client_id,
                    "client_secret": settings.naver_client_secret,
                    "code": payload.code,
                    "state": "naver_login_state" # In real app, verify this state
                }
            )
            if token_res.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to get Naver token")
            
            access_token = token_res.json().get("access_token")
            
            # 2. Get User Info
            user_res = await client.get(
                "https://openapi.naver.com/v1/nid/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            user_response = user_res.json().get("response", {})
            naver_id = user_response.get("id")
            email = user_response.get("email")
            name = user_response.get("name", "Naver User")
            
            uid = f"naver:{naver_id}"

    # 3. Handle Firebase User
    try:
        # Check if user exists
        try:
            firebase_user = auth.get_user_by_email(email) if email else auth.get_user(uid)
        except auth.UserNotFoundError:
            # Create new user
            firebase_user = auth.create_user(
                uid=uid,
                email=email,
                display_name=name
            )
        
        # 4. Create Custom Token
        custom_token = auth.create_custom_token(firebase_user.uid).decode('utf-8')
        return SocialLoginResponse(firebase_custom_token=custom_token)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
