from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DraftCreate(BaseModel):
    title: str
    content_markdown: str = ""
    source_document_id: str | None = None


class DraftFromDocumentCreate(BaseModel):
    title: str | None = None
    include_excerpt_limit: int = 4000


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
