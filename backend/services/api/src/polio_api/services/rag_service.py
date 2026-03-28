"""Lightweight RAG Service

평소에는 가벼운 워크샵 흐름을 유지하며,
심화 모드에서 필요할 때만 KCI/Semantic Scholar 논문을 검색·주입한다.

핵심 원칙:
- 핀된 참고자료가 있을 때만 RAG 컨텍스트를 강화한다
- 참고자료가 없으면 빈 컨텍스트를 반환해 핵심 UX를 해치지 않는다
- 검색 결과는 최대 relevance_budget 내에서 잘라 프롬프트 비용을 통제한다
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from polio_api.services.scholar_service import (
    ScholarPaper,
    ScholarServiceError,
    search_kci_papers,
    search_semantic_scholar_papers,
)


@dataclass(slots=True)
class RAGContext:
    """렌더 프롬프트에 주입할 심화 참고자료 컨텍스트."""

    papers: list[ScholarPaper] = field(default_factory=list)
    internal_chunks: list[Any] = field(default_factory=list)
    pinned_snippets: list[str] = field(default_factory=list)
    injection_text: str = ""
    source_label: str = "none"
    is_enhanced: bool = False


@dataclass(slots=True)
class RAGConfig:
    """RAG 동작 설정."""

    enabled: bool = False
    source: str = "semantic"  # "semantic" | "kci" | "both" | "internal"
    max_papers: int = 3
    max_internal_chunks: int = 5
    relevance_budget_chars: int = 3000
    pin_required: bool = True  # True면 핀된 자료 있을 때만 RAG 발동


def _hash_query(query: str) -> str:
    return hashlib.md5(query.encode("utf-8")).hexdigest()[:12]


def _truncate_abstract(abstract: str | None, max_len: int = 300) -> str:
    if not abstract:
        return "(초록 없음)"
    text = abstract.strip()
    if len(text) <= max_len:
        return text
    return f"{text[:max_len].rstrip()}..."


def _format_paper_context(paper: ScholarPaper) -> str:
    authors = ", ".join(paper.authors[:3])
    if len(paper.authors) > 3:
        authors += " 외"
    year_str = f" ({paper.year})" if paper.year else ""
    citation_str = f" [인용 {paper.citationCount}회]" if paper.citationCount else ""
    return (
        f"📄 {paper.title}{year_str}{citation_str}\n"
        f"   저자: {authors or '미상'}\n"
        f"   요약: {_truncate_abstract(paper.abstract)}"
    )


def _format_pinned_snippets(pinned_references: list[Any]) -> list[str]:
    snippets: list[str] = []
    for ref in pinned_references:
        text = getattr(ref, "text_content", None) or getattr(ref, "content_text", None) or ""
        text = text.strip()
        if text:
            source_type = getattr(ref, "source_type", "manual") or "manual"
            snippets.append(f"📌 [{source_type}] {text[:500]}")
    return snippets


def _format_chunk_context(chunk: Any) -> str:
    doc_name = "uploaded document"
    if hasattr(chunk, "document") and chunk.document:
        doc_name = chunk.document.parse_metadata.get("filename", "document")
    return f"📄 [Source: {doc_name}, Page: {chunk.page_number or '?'}]\n   Content: {chunk.content_text.strip()}"


async def build_rag_context(
    db: Session,
    *,
    project_id: str,
    query_keywords: list[str],
    pinned_references: list[Any],
    config: RAGConfig,
) -> RAGContext:
    """심화 모드 RAG 컨텍스트를 조립한다.

    Args:
        db: DB 세션
        project_id: 프로젝트 ID
        query_keywords: 검색 키워드 (탐구 주제에서 추출)
        pinned_references: 핀된 참고자료 객체 리스트
        config: RAG 설정

    Returns:
        RAGContext: 렌더 프롬프트에 주입할 컨텍스트
    """
    # 비활성화 시 빈 컨텍스트
    if not config.enabled:
        return RAGContext()

    # 핀 필수 모드인데 핀이 없으면 빈 컨텍스트
    # 단, 내부 벡터 검색이 명시적으로 활성화되어 있다면 계속 진행할 수도 있음 (여기서는 핀 필수 원칙 고수)
    if config.pin_required and not pinned_references:
        return RAGContext(source_label="pin_required_but_empty")

    # 핀된 참고자료 정리 (이미 핀된 청크 포함)
    pinned_snippets = _format_pinned_snippets(pinned_references)
    
    # 내부 벡터 검색 결과
    internal_chunks = []
    if config.source in ("internal", "both") and query_keywords:
         from polio_api.services.vector_service import search_relevant_chunks
         full_query = " ".join(query_keywords)
         internal_chunks = search_relevant_chunks(
             db, 
             project_id, 
             full_query, 
             limit=config.max_internal_chunks
         )

    # 키워드 기반 학술 검색
    papers: list[ScholarPaper] = []
    source_label = config.source

    if query_keywords and config.source != "internal":
        combined_query = " ".join(query_keywords[:3])

        try:
            if config.source in ("semantic", "both"):
                semantic_result = await search_semantic_scholar_papers(
                    query=combined_query,
                    limit=config.max_papers,
                )
                papers.extend(semantic_result.papers)

            if config.source in ("kci", "both"):
                kci_result = await search_kci_papers(
                    query=combined_query,
                    limit=config.max_papers,
                )
                papers.extend(kci_result.papers)
        except ScholarServiceError:
            source_label = f"{config.source}_fallback"

    # 이부 제목 기준 학술지 중복 제거
    seen_titles: set[str] = set()
    unique_papers: list[ScholarPaper] = []
    for paper in papers:
        normalized = paper.title.strip().lower()
        if normalized not in seen_titles:
            seen_titles.add(normalized)
            unique_papers.append(paper)
    papers = unique_papers[: config.max_papers]

    # 컨텍스트 텍스트 생성 (budget 내)
    parts: list[str] = []
    char_count = 0

    if pinned_snippets:
        parts.append("=== 핀된 참고자료 ===")
        for snippet in pinned_snippets:
            if char_count + len(snippet) > config.relevance_budget_chars:
                break
            parts.append(snippet)
            char_count += len(snippet)

    if internal_chunks:
        parts.append("\n=== 관련 학생 기록 요약 (내부 자료) ===")
        for chunk in internal_chunks:
            formatted = _format_chunk_context(chunk)
            if char_count + len(formatted) > config.relevance_budget_chars:
                break
            parts.append(formatted)
            char_count += len(formatted)

    if papers:
        parts.append("\n=== 학술 검색 결과 (외부 자료) ===")
        for paper in papers:
            formatted = _format_paper_context(paper)
            if char_count + len(formatted) > config.relevance_budget_chars:
                break
            parts.append(formatted)
            char_count += len(formatted)

    injection_text = "\n".join(parts) if parts else ""

    return RAGContext(
        papers=papers,
        internal_chunks=internal_chunks,
        pinned_snippets=pinned_snippets,
        injection_text=injection_text,
        source_label=source_label,
        is_enhanced=bool(papers or internal_chunks or pinned_snippets),
    )


def extract_query_keywords(
    *,
    target_major: str | None,
    turns: list[Any],
    max_keywords: int = 3,
) -> list[str]:
    """턴 내용과 목표 전공에서 검색 키워드를 추출한다."""
    keywords: list[str] = []

    if target_major:
        keywords.append(target_major)

    for turn in reversed(turns):
        query = getattr(turn, "query", "") or ""
        query = query.strip()
        if len(query) > 5 and query not in keywords:
            # 가장 최근 턴에서 핵심 문구 추출
            keywords.append(query[:60])
        if len(keywords) >= max_keywords:
            break

    return keywords


def build_rag_injection_prompt(rag_context: RAGContext) -> str:
    """RAG 컨텍스트를 렌더 프롬프트에 주입할 형태로 변환한다."""
    if not rag_context.is_enhanced:
        return ""

    return f"""
[심화 모드 참고자료 컨텍스트]
아래 근거 자료는 학생이 핀으로 고정했거나, 핀된 키워드 기반으로 검색한 학술 자료입니다.
- 이 자료는 학생의 주장을 "뒷받침할 가능성이 있는 근거"로만 사용하라.
- 학생이 실제로 읽었다고 단정하지 마라.
- 출처를 명시하고, 학생 해석과 분리하라.

{rag_context.injection_text}

[심화 참고자료 사용 규칙]
- 위 참고자료를 근거로 쓸 때 반드시 출처(논문 제목, 저자, 연도)를 evidence_map에 기록하라.
- 학생이 직접 언급하지 않은 내용은 "관련 자료에 따르면" 형식으로 분리하라.
- 검색 결과와 학생 경험을 섞지 마라.
"""
