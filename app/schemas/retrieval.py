from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from domain.enums import ClaimStatus, DocumentType, FreshnessState, RetrievalConflictState, SourceTier


class RetrievalSearchRequest(BaseModel):
    query_text: str = Field(min_length=2)
    limit: int = Field(default=10, ge=1, le=50)
    source_tiers: list[SourceTier] | None = None
    admissions_year: int | None = None
    university_id: str | None = None
    admission_cycle_id: str | None = None
    admission_track_id: str | None = None
    document_types: list[DocumentType] | None = None
    claim_statuses: list[ClaimStatus] | None = None
    freshness_states: list[FreshnessState] | None = None
    conflict_states: list[RetrievalConflictState] | None = None
    current_cycle_only: bool = False
    approved_claims_only: bool = False
    include_conflicts: bool = True
    include_excluded_sources: bool = False


class RetrievalScoreBreakdownRead(BaseModel):
    lexical_score: float
    vector_score: float
    trust_score: float
    quality_score: float
    freshness_score: float
    source_tier_bonus: float
    official_document_boost: float
    current_cycle_boost: float
    approved_claim_boost: float
    direct_rule_boost: float
    stale_penalty: float
    low_trust_penalty: float
    conflict_penalty: float
    rerank_adjustment: float
    final_score: float


class RetrievalCitationRead(BaseModel):
    citation_key: str
    citation_kind: str
    label: str
    source_name: str | None
    source_tier: SourceTier
    document_id: UUID
    document_version_id: UUID | None
    claim_id: UUID | None
    document_chunk_id: UUID | None
    parsed_block_id: UUID | None
    page_number: int | None
    source_url: str | None
    locator: dict[str, object]
    quoted_text: str | None


class RetrievalConflictRead(BaseModel):
    conflict_id: UUID
    conflict_type: str
    status: str
    severity_score: float
    winning_claim_id: UUID | None
    other_claim_id: UUID
    other_claim_text: str
    other_source_tier: SourceTier
    resolution_note: str | None
    metadata: dict[str, object]


class RetrievalHitRead(BaseModel):
    record_type: str
    record_id: UUID
    document_id: UUID
    text: str
    title: str | None
    source_tier: SourceTier
    freshness_state: FreshnessState
    conflict_state: RetrievalConflictState
    score_breakdown: RetrievalScoreBreakdownRead
    metadata: dict[str, object]
    citation: RetrievalCitationRead
    conflicts: list[RetrievalConflictRead]


class RetrievalDiagnosticsRead(BaseModel):
    candidate_count: int
    lexical_candidate_count: int
    vector_candidate_count: int
    reranked: bool
    backend: str
    excluded_tier4: bool


class RetrievalSearchResponse(BaseModel):
    hits: list[RetrievalHitRead]
    diagnostics: RetrievalDiagnosticsRead
    ranking_policy: dict[str, float]
    applied_filters: dict[str, object]
