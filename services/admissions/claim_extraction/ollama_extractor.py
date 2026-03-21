from __future__ import annotations

from hashlib import sha256
import json

from json import JSONDecodeError

from jsonschema import ValidationError as JsonSchemaValidationError, validate

from services.admissions.claim_extraction.base import ClaimExtractionExecutionResult, ClaimExtractionRequest, ClaimExtractor
from services.admissions.claim_extraction.errors import (
    EmptyExtractionResponseError,
    ExtractionResponseParseError,
    ExtractionSchemaValidationError,
)
from services.admissions.claim_extraction.schemas import ClaimExtractionBatch
from services.admissions.model_gateway import extraction_model_gateway


class StructuredClaimExtractor(ClaimExtractor):
    name = "structured_claim_extractor"

    def build_prompt(self, request: ClaimExtractionRequest) -> str:
        selected_blocks = [
            {
                "chunk_index": chunk.chunk_index,
                "page_number": chunk.page_start,
                "heading_path": chunk.heading_path,
                "text": chunk.content_text,
                "selection_metadata": chunk.metadata_json,
            }
            for chunk in request.chunks
        ]
        serialized = json.dumps(selected_blocks, ensure_ascii=False)
        return (
            request.prompt_template.user_text
            .replace("{{BLOCKS_JSON}}", serialized)
            .replace("{{SCHEMA_JSON}}", request.prompt_template.schema_text)
        )

    def extract(self, request: ClaimExtractionRequest) -> ClaimExtractionExecutionResult:
        if not request.chunks:
            return ClaimExtractionExecutionResult(
                batch=ClaimExtractionBatch(claims=[]),
                provider_name="none",
                model_name=request.model_name or "none",
                latency_ms=0,
                trace_id=None,
                observation_id=None,
                request_payload={"chunks": []},
                response_payload={"claims": []},
                usage_details={},
            )

        prompt = self.build_prompt(request)
        request_payload = {
            "document_id": request.document_id,
            "document_version_id": request.document_version_id,
            "batch_index": request.batch_index,
            "strategy_key": request.strategy_key,
            "chunk_indexes": [chunk.chunk_index for chunk in request.chunks],
            "prompt_key": request.prompt_template.key,
            "prompt_version": request.prompt_template.version,
        }
        result = extraction_model_gateway.generate_json(
            system_prompt=request.prompt_template.system_text,
            user_prompt=prompt,
            prompt_key=request.prompt_template.key,
            prompt_version=request.prompt_template.version,
            model_name_override=request.model_name,
            request_metadata=request_payload,
        )
        raw_payload = result.content_text.strip()
        if not raw_payload:
            raise EmptyExtractionResponseError("Model returned an empty extraction response.")
        try:
            parsed_payload = json.loads(raw_payload)
        except JSONDecodeError as exc:
            raise ExtractionResponseParseError(f"Model returned invalid JSON: {exc}") from exc
        try:
            validate(instance=parsed_payload, schema=request.prompt_template.schema_json)
        except JsonSchemaValidationError as exc:
            raise ExtractionSchemaValidationError(f"Model output failed schema validation: {exc.message}") from exc
        return ClaimExtractionExecutionResult(
            batch=ClaimExtractionBatch.model_validate(parsed_payload),
            provider_name=result.provider_name,
            model_name=result.model_name,
            latency_ms=result.latency_ms,
            trace_id=result.trace_id,
            observation_id=result.observation_id,
            request_payload=request_payload,
            response_payload=parsed_payload,
            usage_details=result.usage_details,
        )

    @staticmethod
    def claim_hash(claim_text: str) -> str:
        return sha256(claim_text.encode("utf-8")).hexdigest()


claim_extractor = StructuredClaimExtractor()
ollama_claim_extractor = claim_extractor
