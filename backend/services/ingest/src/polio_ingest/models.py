from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ParsedChunkPayload:
    chunk_index: int
    page_number: int | None
    char_start: int
    char_end: int
    token_estimate: int
    content_text: str


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
