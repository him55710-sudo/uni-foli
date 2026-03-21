from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, TimestampedReadModel
from domain.enums import EvalExampleKind, LifecycleStatus


class EvalEvidenceSpanCreate(BaseModel):
    document_chunk_id: UUID | None = None
    span_rank: int = Field(default=1, ge=1)
    page_number: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    quoted_text: str = Field(min_length=1)
    label: str | None = Field(default=None, max_length=120)
    metadata_json: dict[str, object] = Field(default_factory=dict)


class EvalEvidenceSpanRead(TimestampedReadModel):
    eval_example_id: UUID
    document_chunk_id: UUID | None
    span_rank: int
    page_number: int | None
    char_start: int | None
    char_end: int | None
    quoted_text: str
    label: str | None
    metadata_json: dict[str, object]


class EvalDatasetExampleCreate(BaseModel):
    dataset_key: str = Field(min_length=2, max_length=120)
    example_key: str = Field(min_length=2, max_length=120)
    example_kind: EvalExampleKind
    status: LifecycleStatus = LifecycleStatus.ACTIVE
    document_id: UUID | None = None
    document_chunk_id: UUID | None = None
    prompt_text: str | None = None
    source_text: str | None = None
    expected_claims_json: dict[str, object] = Field(default_factory=dict)
    expected_flags_json: dict[str, object] = Field(default_factory=dict)
    notes: str | None = None
    metadata_json: dict[str, object] = Field(default_factory=dict)


class EvalDatasetExampleRead(TimestampedReadModel):
    dataset_key: str
    example_key: str
    example_kind: EvalExampleKind
    status: LifecycleStatus
    document_id: UUID | None
    document_chunk_id: UUID | None
    prompt_text: str | None
    source_text: str | None
    expected_claims_json: dict[str, object]
    expected_flags_json: dict[str, object]
    notes: str | None
    metadata_json: dict[str, object]
    evidence_spans: list[EvalEvidenceSpanRead]


class RetrievalEvalCaseCreate(BaseModel):
    dataset_key: str = Field(min_length=2, max_length=120)
    case_key: str = Field(min_length=2, max_length=120)
    status: LifecycleStatus = LifecycleStatus.ACTIVE
    query_text: str = Field(min_length=2)
    filters_json: dict[str, object] = Field(default_factory=dict)
    expected_results_json: dict[str, object] = Field(default_factory=dict)
    notes: str | None = None
    metadata_json: dict[str, object] = Field(default_factory=dict)


class RetrievalEvalCaseRead(TimestampedReadModel):
    dataset_key: str
    case_key: str
    status: LifecycleStatus
    query_text: str
    filters_json: dict[str, object]
    expected_results_json: dict[str, object]
    notes: str | None
    metadata_json: dict[str, object]


class RetrievalEvalRunResult(BaseModel):
    case_id: UUID
    passed: bool
    observed_record_ids: list[str]
    observed_document_ids: list[str]
    observed_citation_keys: list[str]
    diagnostics: dict[str, object]
