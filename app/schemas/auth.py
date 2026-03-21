from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    account_id: UUID
    tenant_id: UUID
    role_slug: str
    email: str


class AuthMeRead(BaseModel):
    account_id: UUID
    tenant_id: UUID
    role_slug: str
    email: str
    full_name: str
    is_admin: bool
    global_access: bool
