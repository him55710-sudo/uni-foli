from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    firebase_uid: str
    email: str | None
    name: str | None
    target_university: str | None
    target_major: str | None
    grade: str | None
    track: str | None
    career: str | None
    admission_type: str | None
    interest_universities: list[str] = []
    created_at: datetime
    updated_at: datetime


class UserProfileUpdate(BaseModel):
    grade: str | None = None
    track: str | None = None
    career: str | None = None
    interest_universities: list[str] | None = None


class UserGoalsUpdate(BaseModel):
    target_university: str | None = None
    target_major: str | None = None
    admission_type: str | None = None
    interest_universities: list[str] | None = None
