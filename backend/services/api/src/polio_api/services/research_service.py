from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from polio_api.core.config import get_settings
from polio_api.core.security import sanitize_public_error
from polio_api.db.models.research_chunk import ResearchChunk
from polio_api.db.models.research_document import ResearchDocument
from polio_api.schemas.research import ResearchSourceCreate
from polio_api.services.vector_service import _cosine_similarity, _lexical_overlap_score, extract_meaningful_terms
from polio_ingest import ResearchPipelineError, normalize_research_source
from polio_ingest.models import ResearchSourceInput
from polio_shared.embeddings import get_embedding_service
from polio_shared.rerankers import get_reranker_service


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _placeholder_hash(project_id: str, payload: ResearchSourceCreate) -> str:
    digest = hashlib.sha256()
    digest.update(project_id.encode("utf-8"))
    digest.update((payload.source_type or "").encode("utf-8"))
    digest.update(str(payload.source_classification).encode("utf-8"))
    digest.update((payload.title or "").encode("utf-8"))
    digest.update((payload.canonical_url or "").encode("utf-8"))
    digest.update((payload.external_id or "").encode("utf-8"))
    return digest.hexdigest()


def create_research_placeholder(
    db: Session,
    *,
    project_id: str,
    payload: ResearchSourceCreate,
) -> ResearchDocument:
    document = ResearchDocument(
        project_id=project_id,
        source_type=payload.source_type,
        source_classification=str(payload.source_classification),
        trust_rank=_trust_rank(str(payload.source_classification)),
        title=(payload.title or payload.canonical_url or payload.external_id or payload.source_type).strip(),
        canonical_url=payload.canonical_url,
        external_id=payload.external_id,
        publisher=payload.publisher,
        published_on=payload.published_on,
        usage_note=payload.usage_note,
        copyright_note=payload.copyright_note,
        content_hash=_placeholder_hash(project_id, payload),
        status="pending",
        author_names=[name.strip() for name in payload.author_names if name.strip()],
        source_metadata={
            **(payload.metadata or {}),
            "queued_payload": {
                "has_text": bool(payload.text),
                "has_html_content": bool(payload.html_content),
                "segment_count": len(payload.transcript_segments),
                "has_abstract": bool(payload.abstract),
                "has_extracted_text": bool(payload.extracted_text),
            },
        },
    )
    db.add(document)
    db.flush()
    return document


def ingest_research_document(
    db: Session,
    *,
    document_id: str,
    payload: dict[str, object],
) -> ResearchDocument:
    document = db.get(ResearchDocument, document_id)
    if document is None:
        raise ValueError(f"Research document not found: {document_id}")

    try:
        normalized = normalize_research_source(
            ResearchSourceInput(
                source_type=str(payload.get("source_type", document.source_type)),
                source_classification=str(payload.get("source_classification", document.source_classification)),
                title=_opt_str(payload.get("title")),
                canonical_url=_opt_str(payload.get("canonical_url")),
                text=_opt_str(payload.get("text")),
                html_content=_opt_str(payload.get("html_content")),
                transcript_segments=[str(item) for item in payload.get("transcript_segments", []) if str(item).strip()],
                abstract=_opt_str(payload.get("abstract")),
                extracted_text=_opt_str(payload.get("extracted_text")),
                publisher=_opt_str(payload.get("publisher")),
                author_names=[str(item) for item in payload.get("author_names", []) if str(item).strip()],
                published_on=document.published_on,
                external_id=_opt_str(payload.get("external_id")),
                usage_note=_opt_str(payload.get("usage_note")) or document.usage_note,
                copyright_note=_opt_str(payload.get("copyright_note")) or document.copyright_note,
                metadata=_coerce_metadata(payload.get("metadata")),
            )
        )
    except ResearchPipelineError as exc:
        document.status = "failed"
        document.last_error = sanitize_public_error(
            str(exc),
            fallback="Research ingestion failed. Retry after checking the provided source data.",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        raise

    if document.chunks:
        db.execute(delete(ResearchChunk).where(ResearchChunk.document_id == document.id))

    settings = get_settings()
    embedding_service = get_embedding_service(
        settings.retrieval_embedding_model,
        dimensions=settings.vector_dimensions,
    )
    embedding_metadata = embedding_service.metadata()
    embeddings = embedding_service.generate_embeddings([chunk.content_text for chunk in normalized.chunks])

    document.title = normalized.title
    document.canonical_url = normalized.canonical_url
    document.external_id = normalized.external_id
    document.source_classification = normalized.source_classification
    document.trust_rank = normalized.trust_rank
    document.publisher = normalized.publisher
    document.usage_note = normalized.usage_note
    document.copyright_note = normalized.copyright_note
    document.content_hash = normalized.content_hash
    document.parser_name = normalized.parser_name
    document.status = "indexed"
    document.last_error = None
    document.content_text = normalized.content_text
    document.content_markdown = normalized.content_markdown
    document.author_names = normalized.author_names
    document.source_metadata = normalized.source_metadata
    document.chunk_count = len(normalized.chunks)
    document.word_count = normalized.word_count
    document.ingested_at = utc_now()

    for index, chunk in enumerate(normalized.chunks):
        db.add(
            ResearchChunk(
                document_id=document.id,
                project_id=document.project_id,
                chunk_index=chunk.chunk_index,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                token_estimate=chunk.token_estimate,
                content_text=chunk.content_text,
                embedding=embeddings[index] if index < len(embeddings) else None,
                embedding_model=embedding_metadata.model_name,
            )
        )

    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def list_research_documents(db: Session, project_id: str) -> list[ResearchDocument]:
    stmt = (
        select(ResearchDocument)
        .where(ResearchDocument.project_id == project_id)
        .order_by(ResearchDocument.updated_at.desc())
    )
    return list(db.scalars(stmt))


def get_research_document(db: Session, document_id: str) -> ResearchDocument | None:
    return db.get(ResearchDocument, document_id)


def list_research_chunks(db: Session, document_id: str) -> list[ResearchChunk]:
    stmt = (
        select(ResearchChunk)
        .where(ResearchChunk.document_id == document_id)
        .order_by(ResearchChunk.chunk_index.asc())
    )
    return list(db.scalars(stmt))


@dataclass(slots=True)
class RetrievedResearchChunk:
    chunk: ResearchChunk
    trust_rank: int
    source_classification: str
    similarity_score: float | None
    rerank_score: float | None
    lexical_overlap_score: float
    freshness_score: float
    score: float


def search_relevant_research_chunks(
    db: Session,
    project_id: str,
    query: str,
    *,
    limit: int = 4,
    candidate_pool: int | None = None,
) -> list[RetrievedResearchChunk]:
    query_text = query.strip()
    if not query_text:
        return []

    settings = get_settings()
    pool_size = max(limit, candidate_pool or settings.retrieval_candidate_pool_size)
    embedding_service = get_embedding_service(
        settings.retrieval_embedding_model,
        dimensions=settings.vector_dimensions,
    )
    query_embedding = embedding_service.encode([query_text])[0].tolist()

    stmt = (
        select(ResearchChunk)
        .options(joinedload(ResearchChunk.document))
        .where(ResearchChunk.project_id == project_id)
        .order_by(ResearchChunk.chunk_index.asc())
    )
    chunks = list(db.scalars(stmt))
    if not chunks:
        return []

    scored: list[RetrievedResearchChunk] = []
    for chunk in chunks:
        similarity = _cosine_similarity(query_embedding, chunk.embedding) if chunk.embedding else None
        lexical_score = _lexical_overlap_score(query_text, chunk.content_text)
        scored.append(
            RetrievedResearchChunk(
                chunk=chunk,
                trust_rank=int(getattr(chunk.document, "trust_rank", 0) or 0),
                source_classification=str(getattr(chunk.document, "source_classification", "EXPERT_COMMENTARY")),
                similarity_score=similarity,
                rerank_score=None,
                lexical_overlap_score=lexical_score,
                freshness_score=_freshness_score(getattr(chunk.document, "published_on", None)),
                score=float(similarity if similarity is not None else lexical_score),
            )
        )

    candidate_rows = sorted(
        scored,
        key=lambda item: (
            item.trust_rank,
            item.similarity_score if item.similarity_score is not None else float("-inf"),
            item.lexical_overlap_score,
            item.freshness_score,
        ),
        reverse=True,
    )[:pool_size]
    if settings.retrieval_reranker_enabled and candidate_rows:
        reranker = get_reranker_service(settings.retrieval_reranker_model)
        rerank_scores = reranker.rerank(query_text, [item.chunk.content_text for item in candidate_rows])
        for item, score in zip(candidate_rows, rerank_scores):
            item.rerank_score = float(score)
            item.score = float(score)

    candidate_rows.sort(
        key=lambda item: (
            item.trust_rank,
            item.rerank_score if item.rerank_score is not None else float("-inf"),
            item.similarity_score if item.similarity_score is not None else float("-inf"),
            item.lexical_overlap_score,
            item.freshness_score,
        ),
        reverse=True,
    )
    return [item for item in candidate_rows if item.score > 0 or item.lexical_overlap_score > 0][:limit]


def build_research_query_text(target_major: str | None, query_keywords: list[str]) -> str:
    parts = [keyword.strip() for keyword in query_keywords if keyword.strip()]
    if target_major and target_major.strip() and target_major.strip() not in parts:
        parts.insert(0, target_major.strip())
    return " ".join(parts[:4]).strip()


def _coerce_metadata(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    return {}


def _opt_str(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _trust_rank(source_classification: str) -> int:
    ranking = {
        "OFFICIAL_SOURCE": 400,
        "STUDENT_OWNED_SOURCE": 300,
        "EXPERT_COMMENTARY": 200,
        "COMMUNITY_POST": 100,
        "SCRAPED_OPINION": 0,
    }
    return ranking.get(str(source_classification).strip().upper(), 0)


def _freshness_score(published_on: date | None) -> float:
    if published_on is None:
        return 0.0
    age_days = max(0, (utc_now().date() - published_on).days)
    if age_days <= 180:
        return 3.0
    if age_days <= 365:
        return 2.0
    if age_days <= 730:
        return 1.0
    return 0.0
