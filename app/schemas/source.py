from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedReadModel
from domain.enums import LifecycleStatus, SourceCategory, SourceTier


class SourceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    organization_name: str | None = Field(default=None, max_length=255)
    base_url: str = Field(max_length=1000)
    source_tier: SourceTier
    source_category: SourceCategory
    is_official: bool = True
    allow_crawl: bool = True
    freshness_days: int = 30
    crawl_policy: dict[str, object] = Field(default_factory=dict)


class SourceRead(TimestampedReadModel):
    slug: str
    name: str
    organization_name: str | None
    base_url: str
    source_tier: SourceTier
    source_category: SourceCategory
    is_official: bool
    allow_crawl: bool
    freshness_days: int
    status: LifecycleStatus
    crawl_policy: dict[str, object]


class SourceFileUploadResponse(BaseModel):
    source_id: str
    ingestion_job_id: str
    file_object_id: str | None
    status: str
