from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GuidedChatStartRequest(BaseModel):
    project_id: str | None = None


class GuidedChatStartResponse(BaseModel):
    greeting: str
    project_id: str | None = None
    evidence_gap_note: str | None = None
    limited_mode: bool | None = None
    limited_reason: str | None = None
    state_summary: dict[str, Any] | None = None


class TopicSuggestion(BaseModel):
    id: str
    title: str
    why_fit_student: str
    link_to_record_flow: str
    link_to_target_major_or_university: str | None = None
    novelty_point: str
    caution_note: str | None = None


class TopicSuggestionRequest(BaseModel):
    project_id: str | None = None
    subject: str = Field(min_length=1, max_length=100)


class TopicSuggestionResponse(BaseModel):
    greeting: str
    subject: str
    suggestions: list[TopicSuggestion]
    evidence_gap_note: str | None = None
    limited_mode: bool | None = None
    limited_reason: str | None = None
    state_summary: dict[str, Any] | None = None


class PageRangeOption(BaseModel):
    label: str
    min_pages: int = Field(ge=1, le=20)
    max_pages: int = Field(ge=1, le=20)
    why_this_length: str


class OutlineSection(BaseModel):
    title: str
    purpose: str


class TopicSelectionRequest(BaseModel):
    project_id: str | None = None
    selected_topic_id: str = Field(min_length=1, max_length=120)
    subject: str | None = Field(default=None, max_length=100)
    suggestions: list[TopicSuggestion] = Field(default_factory=list)


class TopicSelectionResponse(BaseModel):
    selected_topic_id: str
    selected_title: str
    recommended_page_ranges: list[PageRangeOption]
    recommended_outline: list[OutlineSection]
    starter_draft_markdown: str
    guidance_message: str
    limited_mode: bool | None = None
    limited_reason: str | None = None
    state_summary: dict[str, Any] | None = None


class GuidedChatStatePayload(BaseModel):
    subject: str | None = None
    suggestions: list[TopicSuggestion] = Field(default_factory=list)
    selected_topic_id: str | None = None
    recommended_page_ranges: list[PageRangeOption] = Field(default_factory=list)
    recommended_outline: list[OutlineSection] = Field(default_factory=list)
    starter_draft_markdown: str | None = None
    state_summary: dict[str, Any] = Field(default_factory=dict)
    limited_mode: bool | None = None
    limited_reason: str | None = None
