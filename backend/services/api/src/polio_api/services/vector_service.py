from __future__ import annotations

import math
import re
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from polio_api.core.config import get_settings
from polio_api.db.models.document_chunk import DocumentChunk
from polio_shared.embeddings import get_embedding_service
from polio_shared.rerankers import get_reranker_service

TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)
QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "did",
    "do",
    "does",
    "document",
    "documents",
    "enough",
    "evidence",
    "exist",
    "exists",
    "for",
    "from",
    "have",
    "has",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "prove",
    "proves",
    "record",
    "records",
    "show",
    "shows",
    "support",
    "supported",
    "that",
    "the",
    "this",
    "to",
    "uploaded",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "기록",
    "근거",
    "무엇",
    "문서",
    "어떤",
    "어떻게",
    "언제",
    "왜",
    "어디",
    "업로드",
    "증거",
}


@dataclass(slots=True)
class RetrievedChunk:
    chunk: DocumentChunk
    similarity_score: float | None
    rerank_score: float | None
    lexical_overlap_score: float
    score: float


def retrieve_relevant_chunks(
    db: Session,
    project_id: str,
    query: str,
    *,
    limit: int = 5,
    candidate_pool: int | None = None,
    rerank: bool | None = None,
) -> list[RetrievedChunk]:
    settings = get_settings()
    query_text = query.strip()
    if not query_text:
        return []

    use_reranker = settings.retrieval_reranker_enabled if rerank is None else rerank
    pool_size = max(limit, candidate_pool or settings.retrieval_candidate_pool_size)
    embedding_service = get_embedding_service(
        settings.retrieval_embedding_model,
        dimensions=settings.vector_dimensions,
    )
    query_embedding = embedding_service.encode([query_text])[0].tolist()

    if db.bind.dialect.name == "postgresql":
        candidates = _fetch_postgres_candidates(db, project_id, query_embedding, pool_size)
    else:
        candidates = _fetch_python_vector_candidates(db, project_id, query_embedding, pool_size)

    if not candidates:
        candidates = _fetch_lexical_candidates(db, project_id, query_text, pool_size)
        if not candidates:
            return []

    if use_reranker:
        reranker = get_reranker_service(settings.retrieval_reranker_model)
        rerank_scores = reranker.rerank(query_text, [item.chunk.content_text for item in candidates])
        for item, rerank_score in zip(candidates, rerank_scores):
            item.rerank_score = float(rerank_score)

    for item in candidates:
        item.lexical_overlap_score = _lexical_overlap_score(query_text, item.chunk.content_text)
        primary_score = item.rerank_score if item.rerank_score is not None else item.similarity_score
        item.score = float(primary_score if primary_score is not None else item.lexical_overlap_score)

    candidates.sort(
        key=lambda item: (
            item.rerank_score if item.rerank_score is not None else float("-inf"),
            item.similarity_score if item.similarity_score is not None else float("-inf"),
            item.lexical_overlap_score,
            -item.chunk.chunk_index,
        ),
        reverse=True,
    )
    return candidates[:limit]


def search_relevant_chunks(
    db: Session,
    project_id: str,
    query: str,
    *,
    limit: int = 5,
    min_score: float = 0.0,
    rerank: bool = True,
) -> list[DocumentChunk]:
    """Retrieve relevant document chunks for a given query and project."""
    results = retrieve_relevant_chunks(
        db,
        project_id,
        query,
        limit=limit,
        rerank=rerank,
    )
    filtered = [item.chunk for item in results if item.score >= min_score]
    return filtered[:limit]


def drop_project_vectors(db: Session, project_id: str) -> None:
    stmt = delete(DocumentChunk).where(DocumentChunk.project_id == project_id)
    db.execute(stmt)
    db.commit()


def _fetch_postgres_candidates(
    db: Session,
    project_id: str,
    query_embedding: list[float],
    candidate_pool: int,
) -> list[RetrievedChunk]:
    distance_expression = DocumentChunk.embedding.cosine_distance(query_embedding)
    stmt = (
        select(DocumentChunk, distance_expression.label("distance"))
        .options(joinedload(DocumentChunk.document))
        .where(
            DocumentChunk.project_id == project_id,
            DocumentChunk.embedding.is_not(None),
        )
        .order_by(distance_expression.asc(), DocumentChunk.chunk_index.asc())
        .limit(candidate_pool)
    )

    rows = db.execute(stmt).all()
    return [
        RetrievedChunk(
            chunk=chunk,
            similarity_score=max(0.0, 1.0 - float(distance)) if distance is not None else None,
            rerank_score=None,
            lexical_overlap_score=0.0,
            score=0.0,
        )
        for chunk, distance in rows
    ]


def _fetch_python_vector_candidates(
    db: Session,
    project_id: str,
    query_embedding: list[float],
    candidate_pool: int,
) -> list[RetrievedChunk]:
    stmt = (
        select(DocumentChunk)
        .options(joinedload(DocumentChunk.document))
        .where(DocumentChunk.project_id == project_id)
        .order_by(DocumentChunk.chunk_index.asc())
    )
    chunks = list(db.scalars(stmt))
    scored: list[RetrievedChunk] = []
    for chunk in chunks:
        if not chunk.embedding:
            continue
        similarity = _cosine_similarity(query_embedding, chunk.embedding)
        scored.append(
            RetrievedChunk(
                chunk=chunk,
                similarity_score=similarity,
                rerank_score=None,
                lexical_overlap_score=0.0,
                score=0.0,
            )
        )

    scored.sort(
        key=lambda item: (
            item.similarity_score if item.similarity_score is not None else float("-inf"),
            item.chunk.chunk_index,
        ),
        reverse=True,
    )
    return scored[:candidate_pool]


def _fetch_lexical_candidates(
    db: Session,
    project_id: str,
    query: str,
    candidate_pool: int,
) -> list[RetrievedChunk]:
    stmt = (
        select(DocumentChunk)
        .options(joinedload(DocumentChunk.document))
        .where(DocumentChunk.project_id == project_id)
        .order_by(DocumentChunk.chunk_index.asc())
    )
    chunks = list(db.scalars(stmt))
    scored: list[RetrievedChunk] = []
    for chunk in chunks:
        lexical_score = _lexical_overlap_score(query, chunk.content_text)
        if lexical_score <= 0:
            continue
        scored.append(
            RetrievedChunk(
                chunk=chunk,
                similarity_score=None,
                rerank_score=None,
                lexical_overlap_score=lexical_score,
                score=lexical_score,
            )
        )
    scored.sort(key=lambda item: (item.lexical_overlap_score, -item.chunk.chunk_index), reverse=True)
    return scored[:candidate_pool]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def _lexical_overlap_score(query: str, content: str) -> float:
    query_terms = extract_meaningful_terms(query)
    if not query_terms:
        return 0.0
    content_terms = extract_meaningful_terms(content)
    if not content_terms:
        return 0.0
    overlap = len(query_terms & content_terms)
    coverage = overlap / len(query_terms)
    density = overlap / len(content_terms)
    return round((coverage * 0.7) + (density * 0.3), 6)


def extract_meaningful_terms(text: str) -> set[str]:
    return {
        token.lower()
        for token in TOKEN_PATTERN.findall(text or "")
        if token.lower() not in QUERY_STOPWORDS
    }
