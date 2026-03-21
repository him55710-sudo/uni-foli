from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, TimestampedReadModel
from domain.enums import (
    ClaimStatus,
    ClaimType,
    ExtractionBatchStatus,
    ExtractionChunkDecisionStatus,
    ExtractionFailureCode,
    ExtractionJobStatus,
)


class ExtractionBatchRead(TimestampedReadModel):
    extraction_job_id: UUID
    batch_index: int
    status: ExtractionBatchStatus
    model_provider: str
    model_name: str
    prompt_template_key: str
    prompt_template_version: str | None
    attempt_count: int
    chunk_count: int
    latency_ms: int | None
    failure_reason_code: ExtractionFailureCode | None
    trace_id: str | None
    observation_id: str | None
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    request_payload: dict[str, object]
    response_payload: dict[str, object]
    metadata_json: dict[str, object]


class ExtractionJobRead(TimestampedReadModel):
    document_id: UUID
    document_version_id: UUID
    status: ExtractionJobStatus
    extractor_name: str
    model_provider: str
    model_name: str
    prompt_template_key: str
    prompt_template_version: str | None
    selection_policy_key: str | None
    chunk_count: int
    batch_count: int
    successful_batch_count: int
    failed_batch_count: int
    claims_extracted_count: int
    retry_count: int
    failure_reason_code: ExtractionFailureCode | None
    last_latency_ms: int | None
    trace_id: str | None
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    selection_summary_json: dict[str, object]
    job_config: dict[str, object]


class ExtractionChunkDecisionRead(TimestampedReadModel):
    extraction_job_id: UUID
    document_chunk_id: UUID
    status: ExtractionChunkDecisionStatus
    selection_policy_key: str
    priority_score: float
    reason_codes: list[str]
    metadata_json: dict[str, object]


class ClaimReviewUpdate(BaseModel):
    status: ClaimStatus
    reviewer_id: str | None = Field(default=None, max_length=120)
    reviewer_note: str | None = None
    evidence_quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    university_exception_note: str | None = None
    unsafe_flagged: bool | None = None
    overclaim_flagged: bool | None = None
    claim_type: ClaimType | None = None


class BulkLowConfidenceRequest(BaseModel):
    threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    limit: int = Field(default=100, ge=1, le=1000)
    reviewer_id: str | None = Field(default=None, max_length=120)
    reviewer_note: str | None = None


class ExtractionFailureRead(ORMModel):
    extraction_job_id: UUID
    document_id: UUID
    batch_id: UUID
    source_id: UUID | None
    model_provider: str
    model_name: str
    prompt_template_key: str
    prompt_template_version: str | None
    failure_reason_code: ExtractionFailureCode | None
    error_message: str | None
    trace_id: str | None
    created_at: datetime


class ExtractionStatsRead(BaseModel):
    source_id: str | None
    source_name: str | None
    model_provider: str
    model_name: str
    total_jobs: int
    total_batches: int
    failed_batches: int
    claims_extracted_count: int
    avg_latency_ms: float | None
