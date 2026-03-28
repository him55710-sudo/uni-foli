from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from threading import Lock
from typing import Any

try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None

logger = logging.getLogger(__name__)
TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)
MODEL_DOWNLOAD_FLAGS = {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class RerankerServiceMetadata:
    provider: str
    model_name: str
    is_fallback: bool


class RerankerService:
    _instances: dict[str, "RerankerService"] = {}
    _instances_lock = Lock()

    def __new__(cls, model_name: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"):
        with cls._instances_lock:
            instance = cls._instances.get(model_name)
            if instance is None:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instances[model_name] = instance
        return instance

    def __init__(self, model_name: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1") -> None:
        if getattr(self, "_initialized", False):
            return
        self.requested_model_name = model_name
        self._model: Any = None
        self._fallback_reason: str | None = None
        self._load_lock = Lock()
        self._initialized = True

    def metadata(self) -> RerankerServiceMetadata:
        self._ensure_model()
        if self._model is not None:
            return RerankerServiceMetadata(
                provider="sentence-transformers",
                model_name=self.requested_model_name,
                is_fallback=False,
            )
        return RerankerServiceMetadata(
            provider="lexical-fallback",
            model_name=f"lexical-fallback/{self.requested_model_name}",
            is_fallback=True,
        )

    def rerank(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []

        self._ensure_model()
        if self._model is not None:
            pairs = [[query, passage] for passage in passages]
            scores = self._model.predict(pairs)
            return [float(score) for score in scores.tolist()]
        return self._lexical_scores(query, passages)

    def _ensure_model(self) -> None:
        if self._model is not None or self._fallback_reason is not None:
            return

        with self._load_lock:
            if self._model is not None or self._fallback_reason is not None:
                return
            if CrossEncoder is None:
                self._fallback_reason = "sentence-transformers CrossEncoder is not installed"
                return

            allow_downloads = (
                os.getenv("POLIO_ALLOW_MODEL_DOWNLOADS", "").strip().lower() in MODEL_DOWNLOAD_FLAGS
            )
            try:
                kwargs: dict[str, Any] = {}
                if not allow_downloads:
                    kwargs["local_files_only"] = True
                self._model = CrossEncoder(self.requested_model_name, **kwargs)
            except Exception as exc:  # noqa: BLE001
                self._fallback_reason = str(exc)
                logger.warning(
                    "Falling back to lexical reranking for %s: %s",
                    self.requested_model_name,
                    exc,
                )

    def _lexical_scores(self, query: str, passages: list[str]) -> list[float]:
        query_terms = {token.lower() for token in TOKEN_PATTERN.findall(query or "")}
        if not query_terms:
            return [0.0 for _ in passages]

        scores: list[float] = []
        for passage in passages:
            passage_terms = {token.lower() for token in TOKEN_PATTERN.findall(passage or "")}
            if not passage_terms:
                scores.append(0.0)
                continue
            overlap = len(query_terms & passage_terms)
            coverage = overlap / len(query_terms)
            density = overlap / len(passage_terms)
            scores.append(round((coverage * 0.75) + (density * 0.25), 6))
        return scores


def get_reranker_service(model_name: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1") -> RerankerService:
    return RerankerService(model_name)
