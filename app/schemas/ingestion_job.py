from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedReadModel
from domain.enums import IngestionJobStatus


class IngestionJobCreate(BaseModel):
    input_locator: str = Field(max_length=1000)
    source_id: str | None = None
    source_crawl_job_id: str | None = None
    file_object_id: str | None = None
    document_id: str | None = None
    pipeline_stage: str = Field(default="registered", max_length=80)
    trace_json: dict[str, object] = Field(default_factory=dict)


class IngestionJobRead(TimestampedReadModel):
    source_id: UUID | None
    source_crawl_job_id: UUID | None
    file_object_id: UUID | None
    document_id: UUID | None
    input_locator: str
    pipeline_stage: str
    status: IngestionJobStatus
    retry_count: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    trace_json: dict[str, object]
