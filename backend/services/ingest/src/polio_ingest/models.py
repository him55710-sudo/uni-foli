from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(slots=True)
class ParsedChunkPayload:
    chunk_index: int
    page_number: int | None
    char_start: int
    char_end: int
    token_estimate: int
    content_text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParsedDocumentPayload:
    parser_name: str
    source_extension: str
    page_count: int
    word_count: int
    content_text: str
    content_markdown: str
    metadata: dict[str, object]
    chunks: list[ParsedChunkPayload]
    processing_status: str = "parsed"
    masking_status: str = "masked"
    warnings: list[str] = field(default_factory=list)
    raw_artifact: dict[str, Any] = field(default_factory=dict)
    masked_artifact: dict[str, Any] = field(default_factory=dict)
    analysis_artifact: dict[str, Any] = field(default_factory=dict)
    parse_confidence: float = 0.0
    needs_review: bool = False


@dataclass(slots=True)
class ResearchSourceInput:
    source_type: str
    source_classification: str
    title: str | None = None
    canonical_url: str | None = None
    text: str | None = None
    html_content: str | None = None
    transcript_segments: list[str] = field(default_factory=list)
    abstract: str | None = None
    extracted_text: str | None = None
    publisher: str | None = None
    author_names: list[str] = field(default_factory=list)
    published_on: date | None = None
    external_id: str | None = None
    usage_note: str | None = None
    copyright_note: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ResearchChunkPayload:
    chunk_index: int
    char_start: int
    char_end: int
    token_estimate: int
    content_text: str


@dataclass(slots=True)
class ResearchDocumentPayload:
    provenance_type: str
    source_type: str
    source_classification: str
    trust_rank: int
    title: str
    canonical_url: str | None
    external_id: str | None
    publisher: str | None
    published_on: date | None
    usage_note: str | None
    copyright_note: str | None
    parser_name: str
    content_text: str
    content_markdown: str
    author_names: list[str]
    source_metadata: dict[str, Any]
    content_hash: str
    word_count: int
    chunks: list[ResearchChunkPayload]
