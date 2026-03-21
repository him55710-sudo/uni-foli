from __future__ import annotations

from typing import Protocol, TypeVar

from app.core.config import get_settings


HitT = TypeVar("HitT")


class RetrievalReranker(Protocol[HitT]):
    def rerank(self, *, query_text: str, hits: list[HitT]) -> list[HitT]:
        ...


class PassThroughReranker(RetrievalReranker[HitT]):
    def rerank(self, *, query_text: str, hits: list[HitT]) -> list[HitT]:
        return hits


class KeywordPreferenceReranker(RetrievalReranker[HitT]):
    def rerank(self, *, query_text: str, hits: list[HitT]) -> list[HitT]:
        query_terms = {token for token in query_text.lower().split() if token}
        return sorted(
            hits,
            key=lambda hit: (
                -sum(1 for token in query_terms if token in getattr(hit, "text", "").lower()),
                -getattr(getattr(hit, "score_breakdown", None), "final_score", 0.0),
            ),
        )


class RetrievalRerankingService:
    def get_reranker(self) -> RetrievalReranker[object]:
        settings = get_settings()
        if not settings.retrieval_reranker_enabled:
            return PassThroughReranker()
        if settings.retrieval_reranker_provider == "keyword":
            return KeywordPreferenceReranker()
        return PassThroughReranker()


retrieval_reranking_service = RetrievalRerankingService()
