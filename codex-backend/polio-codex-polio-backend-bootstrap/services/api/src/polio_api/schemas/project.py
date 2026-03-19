from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    title: str
    description: str | None = None
    target_university: str | None = None
    target_major: str | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str | None
    target_university: str | None
    target_major: str | None
    status: str
    created_at: datetime
    updated_at: datetime
