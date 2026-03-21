from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import ORMModel, TimestampedReadModel
from domain.enums import ClaimStatus, ClaimType, SourceTier


class ClaimEvidenceRead(ORMModel):
    id: UUID
    parsed_block_id: UUID
    document_chunk_id: UUID | None
    page_number: int | None
    char_start: int | None
    char_end: int | None
    evidence_text: str
    confidence_score: float


class ClaimRead(TimestampedReadModel):
    document_id: UUID
    document_version_id: UUID
    claim_type: ClaimType
    claim_text: str
    normalized_claim_text: str
    source_tier: SourceTier
    applicable_from_year: int | None
    applicable_to_year: int | None
    applicable_cycle_label: str | None
    confidence_score: float
    quality_score: float
    overclaim_risk_score: float
    evidence_quality_score: float
    is_direct_rule: bool
    unsafe_flagged: bool
    overclaim_flagged: bool
    reviewer_note: str | None
    reviewer_id: str | None
    university_exception_note: str | None
    prompt_template_version: str | None
    status: ClaimStatus
    metadata_json: dict[str, object]
    evidence_items: list[ClaimEvidenceRead]


class ClaimExtractionRequestBody(BaseModel):
    document_id: str
    model_name: str | None = None
    chunk_indexes: list[int] | None = None
    strategy_key: str | None = None
    strategy_key: str | None = None


class ClaimStatusUpdate(BaseModel):
    status: ClaimStatus
