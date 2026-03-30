from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    target_university: str | None = Field(default=None, max_length=200)
    target_major: str | None = Field(default=None, max_length=200)


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
