from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, TimestampedReadModel
from domain.enums import CrawlJobStatus, DiscoveredUrlStatus, FileObjectStatus, LifecycleStatus, SourceSeedType, StorageProvider


class SourceSeedCreate(BaseModel):
    source_id: str
    seed_type: SourceSeedType
    label: str = Field(min_length=2, max_length=255)
    seed_url: str = Field(max_length=1000)
    allowed_domains: list[str] = Field(default_factory=list)
    allowed_path_prefixes: list[str] = Field(default_factory=list)
    denied_path_prefixes: list[str] = Field(default_factory=list)
    max_depth: int = Field(default=2, ge=0, le=5)
    current_cycle_year_hint: int | None = None
    allow_binary_assets: bool = True
    respect_robots_txt: bool = True
    metadata_json: dict[str, object] = Field(default_factory=dict)


class SourceSeedRead(TimestampedReadModel):
    source_id: UUID
    seed_type: SourceSeedType
    label: str
    seed_url: str
    allowed_domains: list[str]
    allowed_path_prefixes: list[str]
    denied_path_prefixes: list[str]
    max_depth: int
    current_cycle_year_hint: int | None
    allow_binary_assets: bool
    respect_robots_txt: bool
    status: LifecycleStatus
    last_crawled_at: datetime | None
    last_succeeded_at: datetime | None
    last_error_message: str | None
    metadata_json: dict[str, object]


class CrawlJobCreate(BaseModel):
    source_id: str
    source_seed_id: str
    trigger_mode: str = Field(default="manual", max_length=40)


class CrawlJobRead(TimestampedReadModel):
    source_id: UUID
    source_seed_id: UUID | None
    status: CrawlJobStatus
    trigger_mode: str
    seed_url: str | None
    crawl_scope: str
    discovered_url_count: int
    downloaded_file_count: int
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    job_stats: dict[str, object]


class DiscoveredUrlRead(TimestampedReadModel):
    source_id: UUID
    source_seed_id: UUID
    latest_crawl_job_id: UUID | None
    file_object_id: UUID | None
    document_id: UUID | None
    canonical_url: str
    discovered_from_url: str | None
    depth: int
    content_type: str | None
    http_status: int | None
    etag: str | None
    last_modified_header: str | None
    is_html: bool
    is_downloadable_asset: bool
    is_current_cycle_relevant: bool
    relevance_score: float
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    last_fetched_at: datetime | None
    next_refresh_at: datetime | None
    status: DiscoveredUrlStatus
    metadata_json: dict[str, object]


class FileObjectRead(TimestampedReadModel):
    tenant_id: UUID | None
    storage_provider: StorageProvider
    bucket_name: str | None
    object_key: str
    local_path: str | None
    original_filename: str
    mime_type: str
    size_bytes: int
    md5: str | None
    sha256: str
    source_url: str | None
    retention_expires_at: datetime | None
    purge_after_at: datetime | None
    status: FileObjectStatus
    metadata_json: dict[str, object]


class ParserSummaryRead(ORMModel):
    document_id: UUID
    document_version_id: UUID | None
    parser_name: str | None
    parser_version: str | None
    parser_trace: list[dict[str, object]]
    parser_fallback_reason: str | None
    page_count: int
    block_count: int
    chunk_count: int
    freshness_score: float
    quality_score: float
    is_current_cycle: bool
