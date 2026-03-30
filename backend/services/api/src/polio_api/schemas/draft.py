from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DraftCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content_markdown: str = Field(default="", max_length=100000)
    source_document_id: str | None = None


class DraftFromDocumentCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    include_excerpt_limit: int = Field(default=4000, ge=500, le=20000)


class DraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    source_document_id: str | None
    title: str
    content_markdown: str
    status: str
    created_at: datetime
    updated_at: datetime
