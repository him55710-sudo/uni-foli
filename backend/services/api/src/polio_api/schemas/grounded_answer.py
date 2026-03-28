from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class GroundedAnswerRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=8)


class GroundedAnswerProvenance(BaseModel):
    document_id: str
    chunk_id: str
    provenance_type: str
    source_label: str
    page_number: int | None = None
    char_start: int
    char_end: int
    excerpt: str
    similarity_score: float | None = None
    rerank_score: float | None = None
    lexical_overlap_score: float
    score: float


class GroundedAnswerResponse(BaseModel):
    status: Literal["answered", "insufficient_evidence"]
    answer: str
    insufficient_evidence: bool
    next_safe_action: str
    missing_information: list[str] = Field(default_factory=list)
    provenance: list[GroundedAnswerProvenance] = Field(default_factory=list)
