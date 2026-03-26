from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from polio_domain.enums import BlockType


class CanonicalTable(BaseModel):
    title: str | None = None
    page_number: int | None = None
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class CanonicalBlock(BaseModel):
    block_index: int
    block_type: BlockType
    page_number: int | None = None
    heading_path: list[str] = Field(default_factory=list)
    title: str | None = None
    raw_text: str
    cleaned_text: str
    char_start: int | None = None
    char_end: int | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class CanonicalParseResult(BaseModel):
    parser_name: str
    parser_version: str = "0.1.0"
    title: str | None = None
    issuing_organization: str | None = None
    publication_date: date | None = None
    admissions_year: int | None = None
    cycle_label: str | None = None
    university_name: str | None = None
    track_name: str | None = None
    source_url: str | None = None
    file_hash: str | None = None
    raw_text: str
    cleaned_text: str
    blocks: list[CanonicalBlock] = Field(default_factory=list)
    tables: list[CanonicalTable] = Field(default_factory=list)
    parser_trace: list[dict[str, object]] = Field(default_factory=list)
    fallback_reason: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
