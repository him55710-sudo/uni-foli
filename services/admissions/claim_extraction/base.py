from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from db.models.content import DocumentChunk
from services.admissions.prompt_registry import PromptTemplateBundle
from services.admissions.claim_extraction.schemas import ClaimExtractionBatch


@dataclass(slots=True)
class ClaimExtractionRequest:
    document_id: str
    document_version_id: str
    chunks: list[DocumentChunk]
    source_tier: str
    model_name: str | None
    prompt_template: PromptTemplateBundle
    batch_index: int
    strategy_key: str


@dataclass(slots=True)
class ClaimExtractionExecutionResult:
    batch: ClaimExtractionBatch
    provider_name: str
    model_name: str
    latency_ms: int | None
    trace_id: str | None
    observation_id: str | None
    request_payload: dict[str, object]
    response_payload: dict[str, object]
    usage_details: dict[str, int]


class ClaimExtractor(ABC):
    name = "claim_extractor"

    @abstractmethod
    def extract(self, request: ClaimExtractionRequest) -> ClaimExtractionExecutionResult:
        raise NotImplementedError
