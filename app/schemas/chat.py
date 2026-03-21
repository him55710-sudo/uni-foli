from __future__ import annotations

from pydantic import BaseModel, Field


class ChatQueryRequest(BaseModel):
    query_text: str = Field(min_length=2)
    limit: int = Field(default=5, ge=1, le=20)


class ChatCitationRead(BaseModel):
    label: str
    citation_kind: str
    page_number: int | None
    quoted_text: str | None
    locator_json: dict[str, object]


class ChatQueryResponse(BaseModel):
    answer: str
    safety_flags: list[str]
    citations: list[ChatCitationRead]
