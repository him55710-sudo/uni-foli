from __future__ import annotations

from uuid import UUID

from app.schemas.common import ORMModel, TimestampedReadModel
from domain.enums import DocumentStatus, DocumentType, SourceTier


class DocumentRead(TimestampedReadModel):
    source_id: UUID | None = None
    source_document_key: str | None = None
    canonical_title: str
    document_type: DocumentType
    source_url: str | None
    source_tier: SourceTier
    admissions_year: int | None
    cycle_label: str | None
    trust_score: float
    freshness_score: float
    quality_score: float
    is_current_cycle: bool
    status: DocumentStatus
    metadata_json: dict[str, object]


class ParsedBlockRead(ORMModel):
    id: UUID
    block_index: int
    page_start: int | None
    page_end: int | None
    heading_path: list[str]
    raw_text: str
    cleaned_text: str
    metadata_json: dict[str, object]


class DocumentChunkRead(ORMModel):
    id: UUID
    chunk_index: int
    chunk_hash: str
    page_start: int | None
    page_end: int | None
    heading_path: list[str]
    token_estimate: int
    content_text: str
    metadata_json: dict[str, object]
