from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedReadModel
from domain.enums import PolicyFlagCode, PolicyFlagStatus, ReviewTaskStatus, ReviewTaskType


class ReviewTaskCreate(BaseModel):
    tenant_id: UUID | None = None
    task_type: ReviewTaskType
    target_kind: str = Field(max_length=60)
    target_id: UUID | None = None
    rationale: str = Field(min_length=3)
    priority: int = Field(default=5, ge=1, le=10)
    assigned_to: str | None = None
    metadata_json: dict[str, object] = Field(default_factory=dict)


class ReviewTaskUpdate(BaseModel):
    status: ReviewTaskStatus
    resolution_note: str | None = None
    assigned_to: str | None = None


class ReviewTaskRead(TimestampedReadModel):
    tenant_id: UUID | None
    task_type: ReviewTaskType
    status: ReviewTaskStatus
    target_kind: str
    target_id: UUID | None
    assigned_to: str | None
    priority: int
    rationale: str
    resolution_note: str | None
    metadata_json: dict[str, object]


class PolicyFlagRead(TimestampedReadModel):
    tenant_id: UUID | None
    student_analysis_run_id: UUID | None
    target_kind: str
    target_id: UUID | None
    flag_code: PolicyFlagCode
    severity_score: float
    status: PolicyFlagStatus
    message: str
    evidence_json: dict[str, object]


class DocumentTrustUpdate(BaseModel):
    low_trust: bool
    note: str | None = None
