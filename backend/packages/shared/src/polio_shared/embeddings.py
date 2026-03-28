from __future__ import annotations

import hashlib
import logging
import os
import re
from dataclasses import dataclass
from threading import Lock
from typing import Any, Sequence

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

logger = logging.getLogger(__name__)
TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)
MODEL_DOWNLOAD_FLAGS = {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class EmbeddingServiceMetadata:
    provider: str
    model_name: str
    dimensions: int
    is_fallback: bool


class EmbeddingService:
    _instances: dict[tuple[str, int], "EmbeddingService"] = {}
    _instances_lock = Lock()

    def __new__(
        cls,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        dimensions: int = 1536,
    ):
        key = (model_name, dimensions)
        with cls._instances_lock:
            instance = cls._instances.get(key)
            if instance is None:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instances[key] = instance
        return instance

    def __init__(
        self,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        dimensions: int = 1536,
    ) -> None:
        if getattr(self, "_initialized", False):
            return
        self.requested_model_name = model_name
        self.dimensions = dimensions
        self._model: Any = None
        self._fallback_reason: str | None = None
        self._load_lock = Lock()
        self._initialized = True

    def metadata(self) -> EmbeddingServiceMetadata:
        self._ensure_model()
        if self._model is not None:
            return EmbeddingServiceMetadata(
                provider="sentence-transformers",
                model_name=self.requested_model_name,
                dimensions=self.dimensions,
                is_fallback=False,
            )
        return EmbeddingServiceMetadata(
            provider="hashing-fallback",
            model_name=f"hashing-fallback/{self.requested_model_name}",
            dimensions=self.dimensions,
            is_fallback=True,
        )

    def encode(self, texts: str | Sequence[str]) -> np.ndarray:
        items = [texts] if isinstance(texts, str) else list(texts)
        if not items:
            return np.empty((0, self.dimensions), dtype=np.float32)

        self._ensure_model()
        if self._model is not None:
            embeddings = self._model.encode(
                items,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            array = np.atleast_2d(np.asarray(embeddings, dtype=np.float32))
            return self._adapt_dimensions(array)
        return self._encode_with_hashing(items)

    def generate_embeddings(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self.encode(list(texts))
        return embeddings.tolist()

    def _ensure_model(self) -> None:
        if self._model is not None or self._fallback_reason is not None:
            return

        with self._load_lock:
            if self._model is not None or self._fallback_reason is not None:
                return
            if SentenceTransformer is None:
                self._fallback_reason = "sentence-transformers is not installed"
                return

            allow_downloads = (
                os.getenv("POLIO_ALLOW_MODEL_DOWNLOADS", "").strip().lower() in MODEL_DOWNLOAD_FLAGS
            )
            try:
                kwargs: dict[str, Any] = {}
                if not allow_downloads:
                    kwargs["local_files_only"] = True
                self._model = SentenceTransformer(self.requested_model_name, **kwargs)
            except Exception as exc:  # noqa: BLE001
                self._fallback_reason = str(exc)
                logger.warning(
                    "Falling back to deterministic hashing embeddings for %s: %s",
                    self.requested_model_name,
                    exc,
                )

    def _adapt_dimensions(self, embeddings: np.ndarray) -> np.ndarray:
        current_dimensions = embeddings.shape[1]
        if current_dimensions == self.dimensions:
            return embeddings
        if current_dimensions > self.dimensions:
            return embeddings[:, : self.dimensions]

        padded = np.zeros((embeddings.shape[0], self.dimensions), dtype=np.float32)
        padded[:, :current_dimensions] = embeddings
        return padded

    def _encode_with_hashing(self, texts: Sequence[str]) -> np.ndarray:
        embeddings = np.zeros((len(texts), self.dimensions), dtype=np.float32)
        for row_index, text in enumerate(texts):
            tokens = TOKEN_PATTERN.findall((text or "").lower())
            if not tokens:
                continue
            for token in tokens:
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                column = int.from_bytes(digest[:4], byteorder="big") % self.dimensions
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                embeddings[row_index, column] += sign

            norm = np.linalg.norm(embeddings[row_index])
            if norm > 0:
                embeddings[row_index] /= norm
        return embeddings


def get_embedding_service(
    model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    *,
    dimensions: int = 1536,
) -> EmbeddingService:
    return EmbeddingService(model_name, dimensions)
