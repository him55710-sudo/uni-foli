"""Lightweight RAG service for workshop generation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from polio_api.services.research_service import (
    build_research_query_text,
    search_relevant_research_chunks,
)
from polio_api.services.search_provider_service import (
    normalize_grounding_source_type,
    search_research_sources,
    source_type_label,
)
from polio_api.services.scholar_service import (
    ScholarPaper,
    ScholarServiceError,
)


@dataclass(slots=True)
class RAGContext:
    papers: list[ScholarPaper] = field(default_factory=list)
    internal_chunks: list[Any] = field(default_factory=list)
    research_chunks: list[Any] = field(default_factory=list)
    pinned_snippets: list[str] = field(default_factory=list)
    injection_text: str = ""
    evidence_keys: list[str] = field(default_factory=list)
    source_label: str = "none"
    source_limitation_note: str | None = None
    is_enhanced: bool = False


@dataclass(slots=True)
class RAGConfig:
    enabled: bool = False
    source: str = "semantic"  # "semantic" | "kci" | "both" | "live_web" | "internal"
    max_papers: int = 3
    max_internal_chunks: int = 5
    max_research_chunks: int = 4
    relevance_budget_chars: int = 3000
    pin_required: bool = True
    include_ingested_research: bool = True


def _hash_query(query: str) -> str:
    return hashlib.md5(query.encode("utf-8")).hexdigest()[:12]


def _truncate_abstract(abstract: str | None, max_len: int = 300) -> str:
    if not abstract:
        return "(no abstract)"
    text = abstract.strip()
    if len(text) <= max_len:
        return text
    return f"{text[:max_len].rstrip()}..."


def _format_paper_context(paper: ScholarPaper) -> str:
    authors = ", ".join(paper.authors[:3])
    if len(paper.authors) > 3:
        authors += " et al."
    year_str = f" ({paper.year})" if paper.year else ""
    citation_str = f" [citations: {paper.citationCount}]" if paper.citationCount else ""
    source_type = normalize_grounding_source_type(paper.source_type, fallback="academic_source")
    source_label = paper.source_label or source_type_label(source_type)
    provider = paper.source_provider or "unknown_provider"
    freshness = paper.freshness_label or "unknown"
    domain = f" / Domain: {paper.source_domain}" if paper.source_domain else ""
    link = f"\nURL: {paper.url}" if paper.url else ""
    return (
        f"[EXTERNAL_RESEARCH:{source_type}] {paper.title}{year_str}{citation_str}\n"
        f"Source: {source_label} ({provider}, freshness={freshness}){domain}\n"
        f"Authors: {authors or 'Unknown'}\n"
        f"Summary: {_truncate_abstract(paper.abstract)}{link}"
    )


def _format_pinned_snippets(pinned_references: list[Any]) -> list[str]:
    snippets: list[str] = []
    for ref in pinned_references:
        text = getattr(ref, "text_content", None) or getattr(ref, "content_text", None) or ""
        text = text.strip()
        if not text:
            continue
        source_type = normalize_grounding_source_type(getattr(ref, "source_type", None))
        snippets.append(f"[STUDENT_RECORD:{source_type}] {text[:500]}")
    return snippets


def _format_chunk_context(chunk: Any) -> str:
    doc_name = "uploaded document"
    if hasattr(chunk, "document") and chunk.document:
        doc_name = chunk.document.parse_metadata.get("filename", "document")
    return f"[STUDENT_RECORD:{doc_name}, Page: {chunk.page_number or '?'}]\nContent: {chunk.content_text.strip()}"


def _format_research_chunk_context(chunk: Any) -> str:
    document = getattr(chunk, "document", None)
    if document is None:
        return f"[EXTERNAL_RESEARCH]\nContent: {getattr(chunk, 'content_text', '').strip()}"

    source_classification = getattr(document, "source_classification", "EXPERT_COMMENTARY")
    source_type = "official_guideline" if source_classification == "OFFICIAL_SOURCE" else "academic_source"
    source_label = source_type_label(source_type)
    source_bits = [
        source_label,
        source_classification,
        f"trust={getattr(document, 'trust_rank', 0)}",
        document.title,
    ]
    if document.publisher:
        source_bits.append(document.publisher)
    if document.canonical_url:
        source_bits.append(document.canonical_url)
    return f"[EXTERNAL_RESEARCH:{source_type} | {' | '.join(source_bits)}]\nContent: {chunk.content_text.strip()}"


async def build_rag_context(
    db: Session,
    *,
    project_id: str,
    query_keywords: list[str],
    pinned_references: list[Any],
    config: RAGConfig,
) -> RAGContext:
    if not config.enabled:
        return RAGContext()
    if config.pin_required and not pinned_references:
        return RAGContext(source_label="pin_required_but_empty")

    pinned_snippets = _format_pinned_snippets(pinned_references)

    internal_chunks = []
    if config.source in ("internal", "both") and query_keywords:
        from polio_api.services.vector_service import search_relevant_chunks

        internal_chunks = search_relevant_chunks(
            db,
            project_id,
            " ".join(query_keywords),
            limit=config.max_internal_chunks,
        )

    research_chunks = []
    if config.include_ingested_research and query_keywords:
        research_query = build_research_query_text(None, query_keywords)
        research_chunks = [
            item.chunk
            for item in search_relevant_research_chunks(
                db,
                project_id,
                research_query,
                limit=config.max_research_chunks,
            )
        ]

    papers: list[ScholarPaper] = []
    source_label = config.source
    source_limitation_note: str | None = None
    if query_keywords and config.source != "internal":
        combined_query = " ".join(query_keywords[:3])
        try:
            resolved_source = config.source if config.source in {"semantic", "kci", "both", "live_web"} else "semantic"
            search_result = await search_research_sources(
                query=combined_query,
                limit=config.max_papers,
                source=resolved_source,
            )
            papers.extend(search_result.papers)
            source_label = search_result.source
            source_limitation_note = search_result.limitation_note
            if search_result.fallback_applied:
                source_label = f"{search_result.source}_fallback"
        except ScholarServiceError:
            source_label = f"{config.source}_fallback"

    seen_titles: set[str] = set()
    unique_papers: list[ScholarPaper] = []
    for paper in papers:
        normalized = paper.title.strip().lower()
        if normalized in seen_titles:
            continue
        seen_titles.add(normalized)
        unique_papers.append(paper)
    papers = unique_papers[: config.max_papers]

    parts: list[str] = []
    char_count = 0

    if pinned_snippets:
        parts.append("=== STUDENT_RECORD pinned context ===")
        for snippet in pinned_snippets:
            if char_count + len(snippet) > config.relevance_budget_chars:
                break
            parts.append(snippet)
            char_count += len(snippet)

    if internal_chunks:
        parts.append("\n=== STUDENT_RECORD retrieved evidence ===")
        for chunk in internal_chunks:
            formatted = _format_chunk_context(chunk)
            if char_count + len(formatted) > config.relevance_budget_chars:
                break
            parts.append(formatted)
            char_count += len(formatted)

    if research_chunks:
        parts.append("\n=== EXTERNAL_RESEARCH ingested evidence ===")
        for chunk in research_chunks:
            formatted = _format_research_chunk_context(chunk)
            if char_count + len(formatted) > config.relevance_budget_chars:
                break
            parts.append(formatted)
            char_count += len(formatted)

    if papers:
        parts.append("\n=== EXTERNAL_RESEARCH live search results ===")
        for paper in papers:
            formatted = _format_paper_context(paper)
            if char_count + len(formatted) > config.relevance_budget_chars:
                break
            parts.append(formatted)
            char_count += len(formatted)

    return RAGContext(
        papers=papers,
        internal_chunks=internal_chunks,
        research_chunks=research_chunks,
        pinned_snippets=pinned_snippets,
        injection_text="\n".join(parts) if parts else "",
        evidence_keys=[
            *(f"student:{getattr(chunk, 'id', '')}" for chunk in internal_chunks),
            *(f"research:{getattr(chunk, 'id', '')}" for chunk in research_chunks),
            *(f"paper:{paper.url or _hash_query(paper.title)}" for paper in papers),
        ],
        source_label=source_label,
        source_limitation_note=source_limitation_note,
        is_enhanced=bool(papers or internal_chunks or research_chunks or pinned_snippets),
    )


def extract_query_keywords(
    *,
    target_major: str | None,
    turns: list[Any],
    max_keywords: int = 3,
) -> list[str]:
    keywords: list[str] = []
    if target_major:
        keywords.append(target_major)

    for turn in reversed(turns):
        query = (getattr(turn, "query", "") or "").strip()
        if len(query) <= 5 or query in keywords:
            continue
        keywords.append(query[:60])
        if len(keywords) >= max_keywords:
            break
    return keywords


def build_rag_injection_prompt(rag_context: RAGContext) -> str:
    if not rag_context.is_enhanced:
        return ""

    limitation_block = (
        f"\n[Search Limitation]\n{rag_context.source_limitation_note}\n"
        if rag_context.source_limitation_note
        else ""
    )

    return f"""
[RAG Context]
The evidence below is separated into STUDENT_RECORD and EXTERNAL_RESEARCH.
- Only STUDENT_RECORD can support claims about what the student actually did or achieved.
- EXTERNAL_RESEARCH can support trend analysis, comparisons, architectural references, or recommendation rationale.
- Never convert EXTERNAL_RESEARCH into proof of student actions or outcomes.
- For EXTERNAL_RESEARCH, prefer OFFICIAL_SOURCE first, then STUDENT_OWNED_SOURCE, then EXPERT_COMMENTARY.
- COMMUNITY_POST and SCRAPED_OPINION are weak context only and must not override official guidance.
- Keep provenance explicit in the evidence map and final writing.
{limitation_block}

{rag_context.injection_text}

[Usage Rules]
- Preserve whether each source is STUDENT_RECORD or EXTERNAL_RESEARCH.
- Cite external research as supporting context, not as student evidence.
- If external sources disagree, follow the highest-trust source and say lower-trust material is secondary.
- If the student record is thin, say so directly instead of filling the gap with external sources.
""".strip()
