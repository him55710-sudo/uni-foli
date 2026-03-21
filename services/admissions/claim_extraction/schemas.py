from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal

from domain.enums import ClaimType, EvaluationDimensionCode, SourceTier


class ExtractedClaim(BaseModel):
    claim_text: str = Field(min_length=10)
    normalized_claim_text: str = Field(min_length=10)
    claim_type: ClaimType
    source_tier: SourceTier
    target_evaluation_dimension: EvaluationDimensionCode | None = None
    applicable_from_year: int | None = None
    applicable_to_year: int | None = None
    applicable_cycle_label: str | None = None
    confidence_score: float = Field(ge=0.0, le=1.0)
    evidence_quote: str = Field(min_length=5)
    evidence_page_number: int | None = None
    evidence_chunk_index: int | None = None
    rationale: str | None = None
    evidence_quality_score: float | None = Field(default=None, ge=0.0, le=1.0)


class ClaimExtractionBatch(BaseModel):
    claims: list[ExtractedClaim] = Field(default_factory=list)
