from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import sqrt
from time import perf_counter

from app.core.config import get_settings
from services.admissions.langfuse_service import langfuse_service


@dataclass(slots=True)
class ExtractionModelConfig:
    provider: str
    model_name: str
    api_base: str | None
    api_key: str | None
    timeout_seconds: int
    max_retries: int
    backoff_seconds: float
    batch_size: int

    @property
    def litellm_model(self) -> str:
        if "/" in self.model_name:
            return self.model_name
        return f"{self.provider}/{self.model_name}"


@dataclass(slots=True)
class ModelGatewayResult:
    content_text: str
    provider_name: str
    model_name: str
    latency_ms: int
    raw_response: dict[str, object]
    usage_details: dict[str, int]
    trace_id: str | None
    observation_id: str | None


@dataclass(slots=True)
class EmbeddingModelConfig:
    provider: str
    model_name: str
    api_base: str | None
    api_key: str | None
    dimensions: int

    @property
    def litellm_model(self) -> str:
        if self.provider == "hashing":
            return self.model_name
        if "/" in self.model_name:
            return self.model_name
        return f"{self.provider}/{self.model_name}"


@dataclass(slots=True)
class EmbeddingGatewayResult:
    vectors: list[list[float]]
    provider_name: str
    model_name: str
    latency_ms: int
    raw_response: dict[str, object]
    usage_details: dict[str, int]
    trace_id: str | None
    observation_id: str | None


class ModelGatewayException(Exception):
    def __init__(
        self,
        message: str,
        *,
        provider_name: str,
        model_name: str,
        trace_id: str | None,
        observation_id: str | None,
        latency_ms: int | None,
    ) -> None:
        super().__init__(message)
        self.provider_name = provider_name
        self.model_name = model_name
        self.trace_id = trace_id
        self.observation_id = observation_id
        self.latency_ms = latency_ms


class ExtractionModelGateway:
    def get_config(self, *, model_name_override: str | None = None) -> ExtractionModelConfig:
        settings = get_settings()
        model_name = model_name_override or settings.extraction_model_name
        provider = settings.extraction_model_provider
        api_base = settings.extraction_model_api_base or (settings.ollama_base_url if provider == "ollama" else None)
        return ExtractionModelConfig(
            provider=provider,
            model_name=model_name,
            api_base=api_base,
            api_key=settings.extraction_model_api_key or None,
            timeout_seconds=settings.extraction_timeout_seconds,
            max_retries=settings.extraction_max_retries,
            backoff_seconds=settings.extraction_retry_backoff_seconds,
            batch_size=settings.extraction_batch_size,
        )

    def get_embedding_config(self) -> EmbeddingModelConfig:
        settings = get_settings()
        provider = settings.retrieval_embedding_provider
        model_name = settings.retrieval_embedding_model
        api_base = settings.retrieval_embedding_api_base
        if provider == "ollama" and not api_base:
            api_base = settings.ollama_base_url
        return EmbeddingModelConfig(
            provider=provider,
            model_name=model_name,
            api_base=api_base,
            api_key=settings.retrieval_embedding_api_key or None,
            dimensions=settings.vector_dimensions,
        )

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        prompt_key: str,
        prompt_version: str,
        model_name_override: str | None = None,
        request_metadata: dict[str, object] | None = None,
    ) -> ModelGatewayResult:
        from litellm import completion

        config = self.get_config(model_name_override=model_name_override)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        model_parameters = {"timeout_seconds": config.timeout_seconds, "provider": config.provider}
        observation = langfuse_service.start_generation(
            name="claim_extraction_call",
            input_payload={"messages": messages},
            metadata={"prompt_key": prompt_key, **(request_metadata or {})},
            prompt_version=prompt_version,
            model_name=config.litellm_model,
            model_parameters=model_parameters,
        )
        started = perf_counter()
        try:
            response = completion(
                model=config.litellm_model,
                messages=messages,
                timeout=config.timeout_seconds,
                base_url=config.api_base,
                api_key=config.api_key,
                temperature=0,
            )
        except Exception as exc:
            latency_ms = int((perf_counter() - started) * 1000)
            langfuse_service.finalize_generation(
                observation,
                output_payload=None,
                metadata={"latency_ms": latency_ms, "prompt_key": prompt_key, **(request_metadata or {})},
                model_name=config.litellm_model,
                model_parameters=model_parameters,
                usage_details=None,
                error_message=str(exc),
            )
            raise ModelGatewayException(
                str(exc),
                provider_name=config.provider,
                model_name=config.litellm_model,
                trace_id=observation.trace_id,
                observation_id=observation.observation_id,
                latency_ms=latency_ms,
            ) from exc

        latency_ms = int((perf_counter() - started) * 1000)

        content = ""
        if response.choices:
            message = response.choices[0].message
            content = getattr(message, "content", "") or ""
            if isinstance(content, list):
                content = "".join(
                    item.get("text", "")
                    for item in content
                    if isinstance(item, dict)
                )
        usage = getattr(response, "usage", None)
        if usage is not None and hasattr(usage, "model_dump"):
            usage_details = {key: int(value) for key, value in usage.model_dump().items() if isinstance(value, int)}
        else:
            usage_details = {}

        raw_response = response.model_dump() if hasattr(response, "model_dump") else {}
        langfuse_service.finalize_generation(
            observation,
            output_payload={"content_text": content},
            metadata={"latency_ms": latency_ms, "prompt_key": prompt_key, **(request_metadata or {})},
            model_name=config.litellm_model,
            model_parameters=model_parameters,
            usage_details=usage_details,
        )
        return ModelGatewayResult(
            content_text=content,
            provider_name=config.provider,
            model_name=config.litellm_model,
            latency_ms=latency_ms,
            raw_response=raw_response,
            usage_details=usage_details,
            trace_id=observation.trace_id,
            observation_id=observation.observation_id,
        )

    def embed_texts(self, texts: list[str]) -> EmbeddingGatewayResult:
        config = self.get_embedding_config()
        if config.provider == "hashing":
            vectors = [self._hash_embedding(text, config.dimensions) for text in texts]
            return EmbeddingGatewayResult(
                vectors=vectors,
                provider_name=config.provider,
                model_name=config.litellm_model,
                latency_ms=0,
                raw_response={"provider": "hashing", "count": len(texts)},
                usage_details={},
                trace_id=None,
                observation_id=None,
            )

        from litellm import embedding

        observation = langfuse_service.start_generation(
            name="retrieval_embedding_call",
            input_payload={"text_count": len(texts)},
            metadata={"provider": config.provider, "dimensions": config.dimensions},
            prompt_version=None,
            model_name=config.litellm_model,
            model_parameters={"provider": config.provider, "dimensions": config.dimensions},
        )
        started = perf_counter()
        try:
            response = embedding(
                model=config.litellm_model,
                input=texts,
                api_base=config.api_base,
                api_key=config.api_key,
                dimensions=config.dimensions,
            )
        except Exception as exc:
            latency_ms = int((perf_counter() - started) * 1000)
            langfuse_service.finalize_generation(
                observation,
                output_payload=None,
                metadata={"latency_ms": latency_ms, "provider": config.provider},
                model_name=config.litellm_model,
                model_parameters={"provider": config.provider, "dimensions": config.dimensions},
                usage_details=None,
                error_message=str(exc),
            )
            raise ModelGatewayException(
                str(exc),
                provider_name=config.provider,
                model_name=config.litellm_model,
                trace_id=observation.trace_id,
                observation_id=observation.observation_id,
                latency_ms=latency_ms,
            ) from exc

        latency_ms = int((perf_counter() - started) * 1000)
        raw_response = response.model_dump() if hasattr(response, "model_dump") else {}
        data = getattr(response, "data", None) or []
        vectors = [list(item["embedding"]) for item in data if isinstance(item, dict) and "embedding" in item]
        usage = getattr(response, "usage", None)
        if usage is not None and hasattr(usage, "model_dump"):
            usage_details = {key: int(value) for key, value in usage.model_dump().items() if isinstance(value, int)}
        else:
            usage_details = {}
        langfuse_service.finalize_generation(
            observation,
            output_payload={"vector_count": len(vectors)},
            metadata={"latency_ms": latency_ms, "provider": config.provider},
            model_name=config.litellm_model,
            model_parameters={"provider": config.provider, "dimensions": config.dimensions},
            usage_details=usage_details,
        )
        return EmbeddingGatewayResult(
            vectors=vectors,
            provider_name=config.provider,
            model_name=config.litellm_model,
            latency_ms=latency_ms,
            raw_response=raw_response,
            usage_details=usage_details,
            trace_id=observation.trace_id,
            observation_id=observation.observation_id,
        )

    def cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        numerator = sum(a * b for a, b in zip(left, right, strict=False))
        left_norm = sqrt(sum(value * value for value in left))
        right_norm = sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return max(0.0, min(1.0, numerator / (left_norm * right_norm)))

    def _hash_embedding(self, text: str, dimensions: int) -> list[float]:
        vector = [0.0] * dimensions
        for token in text.split():
            digest = sha256(token.lower().encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], byteorder="big") % dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


extraction_model_gateway = ExtractionModelGateway()
