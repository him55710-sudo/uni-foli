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
    created_at: datetime
    updated_at: datetime


class UserTargetUpdate(BaseModel):
    target_university: str
    target_major: str
