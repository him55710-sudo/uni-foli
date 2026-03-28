from __future__ import annotations

import re

from sqlalchemy.orm import Session

from polio_api.core.config import get_settings
from polio_api.db.models.project import Project
from polio_api.schemas.grounded_answer import GroundedAnswerProvenance, GroundedAnswerResponse
from polio_api.services.vector_service import (
    RetrievedChunk,
    extract_meaningful_terms,
    retrieve_relevant_chunks,
)


def answer_project_question(
    db: Session,
    *,
    project: Project,
    question: str,
    top_k: int | None = None,
) -> GroundedAnswerResponse:
    settings = get_settings()
    limit = top_k or settings.grounded_answer_top_k
    retrieved = retrieve_relevant_chunks(db, project.id, question, limit=limit)
    provenance = [_serialize_provenance(item) for item in retrieved]

    if _has_insufficient_evidence(question, retrieved):
        return GroundedAnswerResponse(
            status="insufficient_evidence",
            answer=(
                "I do not have enough direct support in the uploaded documents to answer that safely "
                "without guessing."
            ),
            insufficient_evidence=True,
            next_safe_action=(
                "Upload a document that states the claim more directly, or narrow the question to a "
                "specific activity, timeframe, or document."
            ),
            missing_information=_build_missing_information(question, retrieved),
            provenance=provenance,
        )

    return GroundedAnswerResponse(
        status="answered",
        answer=_compose_extractive_answer(question, retrieved),
        insufficient_evidence=False,
        next_safe_action=(
            "Use the cited excerpts as the drafting basis. If you need a stronger claim, add a source "
            "that states it directly before expanding the wording."
        ),
        provenance=provenance,
    )


def _has_insufficient_evidence(question: str, retrieved: list[RetrievedChunk]) -> bool:
    if not retrieved:
        return True

    settings = get_settings()
    strongest_similarity = max((item.similarity_score or 0.0) for item in retrieved)
    strongest_overlap = max(item.lexical_overlap_score for item in retrieved)
    query_terms = extract_meaningful_terms(question)
    if query_terms:
        has_direct_support = (
            strongest_overlap >= settings.grounded_answer_min_lexical_overlap
            and strongest_similarity >= settings.grounded_answer_min_similarity
        )
    else:
        has_direct_support = strongest_similarity >= settings.grounded_answer_min_similarity
    return not has_direct_support


def _compose_extractive_answer(question: str, retrieved: list[RetrievedChunk]) -> str:
    lines = [f'For the question "{question.strip()}", the uploaded evidence directly shows:']
    for item in retrieved[:3]:
        lines.append(f"- {_format_provenance_label(item)} {_trim_excerpt(item.chunk.content_text)}")
    lines.append("These points are limited to what the cited excerpts explicitly support.")
    return "\n".join(lines)


def _build_missing_information(question: str, retrieved: list[RetrievedChunk]) -> list[str]:
    query_terms = extract_meaningful_terms(question)
    if not query_terms:
        return ["Narrow the question to a concrete activity, source, or claim that should appear in the record."]
    matched_terms: set[str] = set()
    for item in retrieved:
        matched_terms.update(
            token.lower()
            for token in extract_meaningful_terms(item.chunk.content_text or "")
            if token.lower() in query_terms
        )

    missing_terms = sorted(query_terms - matched_terms)
    if missing_terms:
        return [
            "The current documents do not directly mention: " + ", ".join(missing_terms[:6]) + "."
        ]
    return ["The retrieved excerpts are too weak or indirect to support a grounded answer."]


def _serialize_provenance(item: RetrievedChunk) -> GroundedAnswerProvenance:
    source_label = "uploaded document"
    if item.chunk.document is not None:
        source_label = item.chunk.document.original_filename or source_label

    return GroundedAnswerProvenance(
        document_id=item.chunk.document_id,
        chunk_id=item.chunk.id,
        source_label=source_label,
        page_number=item.chunk.page_number,
        char_start=item.chunk.char_start,
        char_end=item.chunk.char_end,
        excerpt=_trim_excerpt(item.chunk.content_text, limit=280),
        similarity_score=item.similarity_score,
        rerank_score=item.rerank_score,
        lexical_overlap_score=item.lexical_overlap_score,
        score=item.score,
    )


def _format_provenance_label(item: RetrievedChunk) -> str:
    source_label = "uploaded document"
    if item.chunk.document is not None:
        source_label = item.chunk.document.original_filename or source_label
    if item.chunk.page_number is not None:
        return f"[{source_label}, page {item.chunk.page_number}]"
    return f"[{source_label}]"


def _trim_excerpt(text: str, *, limit: int = 220) -> str:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."
