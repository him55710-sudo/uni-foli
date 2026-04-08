from __future__ import annotations

import re
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from polio_api.db.models.document_chunk import DocumentChunk
from polio_api.db.models.parsed_document import ParsedDocument
from polio_api.db.models.project import Project
from polio_domain.enums import DocumentProcessingStatus

GroundingProfile = Literal["fast", "standard", "render"]

_TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)
_STOPWORDS = {
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
    "for",
    "from",
    "have",
    "has",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "기록",
    "문서",
    "근거",
    "학생",
    "보고서",
}

_PROFILE_LIMITS: dict[GroundingProfile, tuple[int, int]] = {
    "fast": (1, 2),
    "standard": (2, 4),
    "render": (3, 6),
}


def build_workshop_document_grounding_context(
    *,
    db: Session,
    project: Project | None,
    user_message: str,
    max_documents: int | None = None,
    max_chunks: int | None = None,
    profile: GroundingProfile = "standard",
) -> str:
    profile_limits = _PROFILE_LIMITS.get(profile, _PROFILE_LIMITS["standard"])
    resolved_docs = max_documents if max_documents is not None else profile_limits[0]
    resolved_chunks = max_chunks if max_chunks is not None else profile_limits[1]

    if project is None:
        return (
            "[업로드 문서 근거]\n"
            "연결된 프로젝트가 없어 문서 근거를 불러올 수 없습니다.\n\n"
            "[문서 근거 사용 원칙]\n"
            "- 확인된 텍스트 근거가 없으면 모른다고 답합니다.\n"
            "- 추측으로 학생 활동을 만들지 않습니다."
        )

    documents = _load_recent_documents(db=db, project_id=project.id, limit=resolved_docs)
    document_block = _format_document_analysis_block(documents)

    chunks = _load_recent_chunks(db=db, project_id=project.id, limit=320)
    lexical_chunks = _select_lexical_chunks(chunks=chunks, query=user_message, limit=resolved_chunks)
    evidence_block = _format_chunk_evidence_block(lexical_chunks)

    return (
        f"{document_block}\n\n"
        f"{evidence_block}\n\n"
        "[문서 근거 사용 원칙]\n"
        "- 위 근거 범위를 벗어나는 사실은 단정하지 않습니다.\n"
        "- 부족한 정보는 '추가 확인 필요'로 안내합니다.\n"
        "- 과장 또는 합격 보장 표현은 금지합니다."
    )


def _load_recent_documents(*, db: Session, project_id: str, limit: int) -> list[ParsedDocument]:
    valid_statuses = [
        DocumentProcessingStatus.PARSED.value,
        DocumentProcessingStatus.PARTIAL.value,
    ]
    return list(
        db.execute(
            select(ParsedDocument)
            .where(
                ParsedDocument.project_id == project_id,
                ParsedDocument.status.in_(valid_statuses),
            )
            .order_by(ParsedDocument.updated_at.desc())
            .limit(limit)
        ).scalars()
    )


def _load_recent_chunks(*, db: Session, project_id: str, limit: int) -> list[DocumentChunk]:
    return list(
        db.execute(
            select(DocumentChunk)
            .options(joinedload(DocumentChunk.document))
            .where(DocumentChunk.project_id == project_id)
            .order_by(DocumentChunk.created_at.desc(), DocumentChunk.chunk_index.desc())
            .limit(limit)
        ).scalars()
    )


def _format_document_analysis_block(documents: list[ParsedDocument]) -> str:
    if not documents:
        return "[업로드 문서 분석 요약]\n분석 가능한 문서가 아직 없습니다."

    lines = ["[업로드 문서 분석 요약]"]
    for index, document in enumerate(documents, start=1):
        filename = _clip(document.original_filename or "업로드 문서", limit=72)
        lines.append(
            f"{index}. 파일: {filename} / 페이지: {document.page_count} / 단어: {document.word_count} / 상태: {document.status}"
        )

        pdf_analysis = _extract_pdf_analysis(document.parse_metadata)
        if pdf_analysis:
            summary = _clip(pdf_analysis.get("summary"), limit=260)
            if summary:
                lines.append(f"   - 분석 요약: {summary}")
            key_points = _normalize_list(pdf_analysis.get("key_points"), limit=2, item_limit=160)
            for point in key_points:
                lines.append(f"   - 핵심 포인트: {point}")
            evidence_gaps = _normalize_list(pdf_analysis.get("evidence_gaps"), limit=1, item_limit=160)
            for gap in evidence_gaps:
                lines.append(f"   - 근거 한계: {gap}")
            continue

        fallback_excerpt = _clip(document.content_markdown or document.content_text, limit=220)
        if fallback_excerpt:
            lines.append(f"   - 본문 발췌: {fallback_excerpt}")
    return "\n".join(lines)


def _format_chunk_evidence_block(chunks: list[DocumentChunk]) -> str:
    if not chunks:
        return "[질문 관련 문서 발췌]\n현재 질문과 직접 연결되는 문서 발췌를 찾지 못했습니다."

    lines = ["[질문 관련 문서 발췌]"]
    for index, chunk in enumerate(chunks, start=1):
        doc_name = "업로드 문서"
        if chunk.document is not None:
            doc_name = _clip(chunk.document.original_filename or "업로드 문서", limit=56)
        page_hint = f"p.{chunk.page_number}" if chunk.page_number else "p.?"
        excerpt = _clip(chunk.content_text, limit=180)
        lines.append(f"{index}. {doc_name} ({page_hint})")
        lines.append(f"   - {excerpt}")
    return "\n".join(lines)


def _select_lexical_chunks(*, chunks: list[DocumentChunk], query: str, limit: int) -> list[DocumentChunk]:
    query_terms = _meaningful_terms(query)
    if not query_terms:
        return chunks[:limit]

    scored: list[tuple[float, int, DocumentChunk]] = []
    for chunk in chunks:
        content_terms = _meaningful_terms(chunk.content_text)
        if not content_terms:
            continue
        overlap = len(query_terms & content_terms)
        if overlap <= 0:
            continue

        overlap_ratio = overlap / max(1, len(query_terms))
        length_penalty = min(0.18, max(0.0, (len((chunk.content_text or "")) - 900) / 6000))
        recency_bonus = 0.06 if (chunk.chunk_index or 0) > 0 else 0.0
        score = overlap_ratio + recency_bonus - length_penalty
        scored.append((score, chunk.chunk_index or 0, chunk))

    if not scored:
        return chunks[:limit]

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    ordered: list[DocumentChunk] = []
    seen_ids: set[str] = set()
    for _, _, chunk in scored:
        if chunk.id in seen_ids:
            continue
        seen_ids.add(chunk.id)
        ordered.append(chunk)
        if len(ordered) >= limit:
            break
    return ordered


def _extract_pdf_analysis(metadata: Any) -> dict[str, Any] | None:
    if not isinstance(metadata, dict):
        return None
    candidate = metadata.get("pdf_analysis")
    if isinstance(candidate, dict):
        return candidate
    return None


def _normalize_list(value: Any, *, limit: int, item_limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized = [_clip(str(item), limit=item_limit) for item in value if str(item).strip()]
    return normalized[:limit]


def _meaningful_terms(text: str) -> set[str]:
    return {
        token.lower()
        for token in _TOKEN_PATTERN.findall(text or "")
        if token and token.lower() not in _STOPWORDS
    }


def _clip(value: str | None, *, limit: int) -> str:
    normalized = " ".join((value or "").split()).strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3].rstrip()}..."
