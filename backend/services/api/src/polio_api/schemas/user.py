from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
    interest_universities: list[str] | None = []
    created_at: datetime
    updated_at: datetime


class UserProfileUpdate(BaseModel):
    grade: str | None = Field(default=None, max_length=50)
    track: str | None = Field(default=None, max_length=100)
    career: str | None = Field(default=None, max_length=200)
    interest_universities: list[str] | None = Field(default=None, max_length=20)


class UserGoalsUpdate(BaseModel):
    target_university: str | None = Field(default=None, max_length=200)
    target_major: str | None = Field(default=None, max_length=200)
    admission_type: str | None = Field(default=None, max_length=100)
    interest_universities: list[str] | None = Field(default=None, max_length=20)
