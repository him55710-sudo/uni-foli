from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

import httpx

from polio_domain.enums import EvidenceProvenance, ResearchSourceClassification
from polio_ingest.models import (
    ResearchChunkPayload,
    ResearchDocumentPayload,
    ResearchSourceInput,
)


TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)

TRUST_RANK_BY_CLASSIFICATION = {
    ResearchSourceClassification.OFFICIAL_SOURCE.value: 400,
    ResearchSourceClassification.STUDENT_OWNED_SOURCE.value: 300,
    ResearchSourceClassification.EXPERT_COMMENTARY.value: 200,
    ResearchSourceClassification.COMMUNITY_POST.value: 100,
    ResearchSourceClassification.SCRAPED_OPINION.value: 0,
}

DEFAULT_USAGE_NOTE_BY_CLASSIFICATION = {
    ResearchSourceClassification.OFFICIAL_SOURCE.value: (
        "Use as high-trust external context. Do not treat it as proof of student action."
    ),
    ResearchSourceClassification.STUDENT_OWNED_SOURCE.value: (
        "Use as user-provided background material, not as evidence of student achievements."
    ),
    ResearchSourceClassification.EXPERT_COMMENTARY.value: (
        "Use as supporting interpretation only. Do not let commentary override official guidance."
    ),
    ResearchSourceClassification.COMMUNITY_POST.value: (
        "Use only as low-trust context. It cannot establish policy, outcomes, or student facts."
    ),
    ResearchSourceClassification.SCRAPED_OPINION.value: (
        "Use only as weak context if no better source exists. Never rely on it for claims."
    ),
}


class ResearchPipelineError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class _NormalizedResearchSource:
    parser_name: str
    title: str
    content_text: str
    content_markdown: str
    canonical_url: str | None
    source_metadata: dict[str, Any]


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title: str | None = None
        self.current_tag = "p"
        self.in_title = False
        self.fragments: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        self.current_tag = tag.lower()
        if self.current_tag == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False
        if tag.lower() in {"p", "div", "section", "article", "li", "tr", "br", "h1", "h2", "h3", "h4"}:
            self.fragments.append(("break", "\n"))

    def handle_data(self, data: str) -> None:
        cleaned = data.strip()
        if not cleaned:
            return
        if self.in_title and not self.title:
            self.title = cleaned
        self.fragments.append((self.current_tag, cleaned))


def normalize_research_source(source: ResearchSourceInput) -> ResearchDocumentPayload:
    normalized = _normalize_input(source)
    source_classification = _normalize_source_classification(source.source_classification)
    chunks = [
        ResearchChunkPayload(
            chunk_index=index,
            char_start=char_start,
            char_end=char_end,
            token_estimate=_estimate_tokens(chunk_text),
            content_text=chunk_text,
        )
        for index, (chunk_text, char_start, char_end) in enumerate(_slice_text(normalized.content_text, 1200, 180))
    ]
    if not chunks:
        raise ResearchPipelineError("Research content is empty after normalization.")

    content_hash = hashlib.sha256(
        "\n".join(
            [
                source.source_type.strip().lower(),
                normalized.title,
                normalized.canonical_url or "",
                normalized.content_text,
            ]
        ).encode("utf-8")
    ).hexdigest()

    return ResearchDocumentPayload(
        provenance_type=EvidenceProvenance.EXTERNAL_RESEARCH.value,
        source_type=source.source_type.strip().lower(),
        source_classification=source_classification,
        trust_rank=TRUST_RANK_BY_CLASSIFICATION[source_classification],
        title=normalized.title,
        canonical_url=normalized.canonical_url,
        external_id=source.external_id,
        publisher=(source.publisher or "").strip() or None,
        published_on=source.published_on,
        usage_note=(source.usage_note or "").strip() or DEFAULT_USAGE_NOTE_BY_CLASSIFICATION[source_classification],
        copyright_note=(source.copyright_note or "").strip() or None,
        parser_name=normalized.parser_name,
        content_text=normalized.content_text,
        content_markdown=normalized.content_markdown,
        author_names=[author.strip() for author in source.author_names if author.strip()],
        source_metadata={
            **(source.metadata or {}),
            **normalized.source_metadata,
            "source_format": source.source_type.strip().lower(),
            "source_classification": source_classification,
        },
        content_hash=content_hash,
        word_count=len(TOKEN_PATTERN.findall(normalized.content_text)),
        chunks=chunks,
    )


def _normalize_input(source: ResearchSourceInput) -> _NormalizedResearchSource:
    source_type = source.source_type.strip().lower()
    if source_type not in {"web_article", "youtube_transcript", "paper", "pdf_document"}:
        raise ResearchPipelineError(f"Unsupported research source type: {source.source_type}")

    if source_type == "youtube_transcript":
        return _normalize_youtube_transcript(source)
    if source_type in {"paper", "pdf_document"}:
        return _normalize_paper(source)
    return _normalize_web_article(source)


def _normalize_web_article(source: ResearchSourceInput) -> _NormalizedResearchSource:
    parser_name = "research_pipeline.text"
    content_text = _normalize_text(source.text or "")
    content_markdown = content_text
    metadata: dict[str, Any] = {"normalized_from": "text"}
    parsed_title: str | None = None

    if not content_text and source.html_content:
        parsed_title, content_text, content_markdown = _parse_html(source.html_content)
        parser_name = "research_pipeline.html"
        metadata["normalized_from"] = "html_content"

    if not content_text and source.canonical_url:
        fetched_html = _fetch_url_text(source.canonical_url)
        parsed_title, content_text, content_markdown = _parse_html(fetched_html)
        parser_name = "research_pipeline.web_fetch"
        metadata["normalized_from"] = "canonical_url"

    if not content_text:
        raise ResearchPipelineError("Web article ingestion requires text, html_content, or a reachable canonical_url.")

    title = (source.title or "").strip() or parsed_title or "External article"
    return _NormalizedResearchSource(
        parser_name=parser_name,
        title=title,
        content_text=content_text,
        content_markdown=content_markdown,
        canonical_url=source.canonical_url,
        source_metadata=metadata,
    )


def _normalize_youtube_transcript(source: ResearchSourceInput) -> _NormalizedResearchSource:
    transcript_text = source.text or "\n".join(segment.strip() for segment in source.transcript_segments if segment.strip())
    content_text = _normalize_text(transcript_text)
    if not content_text:
        raise ResearchPipelineError("YouTube transcript ingestion requires transcript text or transcript segments.")

    title = (source.title or "").strip() or "YouTube transcript"
    return _NormalizedResearchSource(
        parser_name="research_pipeline.youtube_transcript",
        title=title,
        content_text=content_text,
        content_markdown=content_text,
        canonical_url=source.canonical_url,
        source_metadata={
            "normalized_from": "transcript",
            "segment_count": len(source.transcript_segments),
        },
    )


def _normalize_paper(source: ResearchSourceInput) -> _NormalizedResearchSource:
    body_parts = [
        (source.abstract or "").strip(),
        (source.extracted_text or "").strip(),
        (source.text or "").strip(),
    ]
    content_text = _normalize_text("\n\n".join(part for part in body_parts if part))
    if not content_text:
        raise ResearchPipelineError("Paper ingestion requires abstract, extracted_text, or text.")

    title = (source.title or "").strip() or "Research paper"
    normalized_from = "pdf_text" if source.source_type.strip().lower() == "pdf_document" else "paper_text"
    metadata = {"normalized_from": normalized_from}
    if source.abstract:
        metadata["has_abstract"] = True
    if source.extracted_text:
        metadata["has_extracted_text"] = True

    content_markdown = "\n\n".join(
        section
        for section in [
            f"# {title}",
            f"Publisher: {source.publisher}" if source.publisher else "",
            "## Abstract\n" + source.abstract.strip() if source.abstract else "",
            "## Extracted Text\n" + source.extracted_text.strip() if source.extracted_text else source.text or "",
        ]
        if section
    )

    return _NormalizedResearchSource(
        parser_name=f"research_pipeline.{'pdf_document' if normalized_from == 'pdf_text' else 'paper'}",
        title=title,
        content_text=content_text,
        content_markdown=content_markdown,
        canonical_url=source.canonical_url,
        source_metadata=metadata,
    )


def _normalize_source_classification(value: str) -> str:
    normalized = (value or "").strip().upper()
    if normalized in TRUST_RANK_BY_CLASSIFICATION:
        return normalized
    raise ResearchPipelineError(f"Unsupported research source classification: {value}")


def _parse_html(html: str) -> tuple[str | None, str, str]:
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    lines: list[str] = []
    markdown_parts: list[str] = []
    heading_path: list[str] = []
    for tag, fragment in extractor.fragments:
        if tag == "break":
            continue
        lines.append(fragment)
        if tag in {"h1", "h2", "h3", "h4"}:
            level = int(tag[1])
            heading_path = heading_path[: max(0, level - 1)]
            heading_path.append(fragment)
            markdown_parts.append(f"{'#' * level} {fragment}")
        else:
            markdown_parts.append(fragment)
    return extractor.title, _normalize_text("\n".join(lines)), "\n\n".join(markdown_parts).strip()


def _fetch_url_text(url: str) -> str:
    try:
        response = httpx.get(url, timeout=10.0, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ResearchPipelineError(f"Unable to fetch research source from {url}: {exc}") from exc
    return response.text


def _slice_text(text: str, chunk_size_chars: int, overlap_chars: int) -> list[tuple[str, int, int]]:
    normalized = _normalize_text(text)
    if not normalized:
        return []

    chunks: list[tuple[str, int, int]] = []
    start = 0
    text_length = len(normalized)
    while start < text_length:
        end = min(text_length, start + chunk_size_chars)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append((chunk, start, end))
        if end >= text_length:
            break
        start = max(0, end - overlap_chars)
    return chunks


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _estimate_tokens(value: str) -> int:
    return max(1, len(value.split()) if value.strip() else 0)
