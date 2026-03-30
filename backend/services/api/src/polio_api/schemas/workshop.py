from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polio_domain.enums import QualityLevel, TurnType, VisualApprovalStatus, WorkshopStatus


class StarterChoice(BaseModel):
    id: str
    label: str
    description: str | None = None
    payload: dict[str, Any] | None = None


class FollowupChoice(BaseModel):
    id: str
    label: str
    description: str | None = None
    payload: dict[str, Any] | None = None


class WorkshopTurnBase(BaseModel):
    turn_type: str = TurnType.MESSAGE.value
    query: str
    action_payload: dict[str, Any] | None = None
    response: str | None = None


class WorkshopTurnCreate(WorkshopTurnBase):
    pass


class WorkshopTurnResponse(WorkshopTurnBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    session_id: str
    created_at: datetime
    updated_at: datetime


class PinnedReferenceBase(BaseModel):
    text_content: str = Field(min_length=1, max_length=6000)
    source_type: str | None = Field(default=None, max_length=32)
    source_id: str | None = Field(default=None, max_length=128)


class PinnedReferenceCreate(PinnedReferenceBase):
    pass


class PinnedReferenceResponse(PinnedReferenceBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    session_id: str
    created_at: datetime


class WorkshopSessionBase(BaseModel):
    project_id: str
    quest_id: str | None = None
    status: str = WorkshopStatus.IDLE.value
    context_score: int = 0
    quality_level: QualityLevel = QualityLevel.MID.value


class WorkshopSessionCreate(BaseModel):
    project_id: str
    quest_id: str | None = None
    quality_level: QualityLevel = QualityLevel.MID.value


class WorkshopQualityUpdateRequest(BaseModel):
    quality_level: QualityLevel


class WorkshopSessionResponse(WorkshopSessionBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime
    turns: list[WorkshopTurnResponse] = Field(default_factory=list)
    pinned_references: list[PinnedReferenceResponse] = Field(default_factory=list)


class WorkshopChoiceRequest(BaseModel):
    choice_id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=300)
    payload: dict[str, Any] | None = None


class WorkshopMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)

class WorkshopSaveDraftRequest(BaseModel):
    document_content: str = Field(min_length=1, max_length=100000)


class WorkshopUpdateVisualRequest(BaseModel):
    approval_status: VisualApprovalStatus
    user_note: str | None = None


class QualityLevelInfo(BaseModel):
    level: QualityLevel
    label: str
    emoji: str
    color: str
    description: str
    detail: str
    student_fit: str
    safety_posture: str
    authenticity_policy: str
    hallucination_guardrail: str
    starter_mode: str
    followup_mode: str
    reference_policy: str
    reference_intensity: str
    render_depth: str
    expression_policy: str
    advanced_features_allowed: bool
    minimum_turn_count: int
    minimum_reference_count: int
    render_threshold: int


class RenderRequirementInfo(BaseModel):
    required_context_score: int
    minimum_turn_count: int
    minimum_reference_count: int
    current_context_score: int
    current_turn_count: int
    current_reference_count: int
    can_render: bool
    missing: list[str] = Field(default_factory=list)


class SafetyDimensionResponse(BaseModel):
    key: str
    label: str
    score: int
    status: str
    detail: str
    matched_count: int = 0
    unsupported_count: int = 0


class QualityControlMetadataResponse(BaseModel):
    schema_version: str
    requested_level: QualityLevel
    requested_label: str
    applied_level: QualityLevel
    applied_label: str
    student_fit: str
    safety_posture: str
    authenticity_policy: str
    hallucination_guardrail: str
    starter_mode: str
    followup_mode: str
    reference_policy: str
    reference_intensity: str
    render_depth: str
    expression_policy: str
    advanced_features_allowed: bool
    advanced_features_requested: bool = False
    advanced_features_applied: bool = False
    advanced_features_reason: str | None = None
    minimum_turn_count: int
    minimum_reference_count: int
    turn_count: int
    reference_count: int
    safety_score: int | None = None
    downgraded: bool = False
    summary: str | None = None
    flags: dict[str, str] = Field(default_factory=dict)
    checks: dict[str, SafetyDimensionResponse] = Field(default_factory=dict)
    repair_applied: bool = False
    repair_strategy: str | None = None


class DraftArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    session_id: str
    report_markdown: str | None = None
    teacher_record_summary_500: str | None = None
    student_submission_note: str | None = None
    evidence_map: dict[str, Any] | None = None
    visual_specs: list[dict[str, Any]] = Field(default_factory=list)
    math_expressions: list[dict[str, Any]] = Field(default_factory=list)
    render_status: str
    error_message: str | None = None
    quality_level_applied: QualityLevel | None = None
    safety_score: int | None = None
    safety_flags: dict[str, str] | None = None
    quality_downgraded: bool = False
    quality_control_meta: QualityControlMetadataResponse | None = None
    created_at: datetime
    updated_at: datetime


class RenderRequest(BaseModel):
    force: bool = False
    advanced_mode: bool = False
    rag_source: str = "semantic"  # "semantic" | "kci" | "both"


class StreamTokenResponse(BaseModel):
    stream_token: str
    workshop_id: str
    expires_in: int = 300


class RenderStatusResponse(BaseModel):
    artifact_id: str
    render_status: str
    message: str | None = None


class SafetyCheckResponse(BaseModel):
    safety_score: int
    flags: dict[str, str]
    recommended_level: QualityLevel
    downgraded: bool
    summary: str
    checks: dict[str, SafetyDimensionResponse] = Field(default_factory=dict)


class WorkshopStateResponse(BaseModel):
    session: WorkshopSessionResponse
    starter_choices: list[StarterChoice] = Field(default_factory=list)
    followup_choices: list[FollowupChoice] = Field(default_factory=list)
    message: str | None = None
    quality_level_info: QualityLevelInfo
    available_quality_levels: list[QualityLevelInfo] = Field(default_factory=list)
    render_requirements: RenderRequirementInfo
    latest_artifact: DraftArtifactResponse | None = None
