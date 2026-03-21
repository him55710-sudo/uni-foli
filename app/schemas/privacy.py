from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedReadModel
from domain.enums import DeletionMode, DeletionRequestStatus, PrivacyMaskingMode, PrivacyScanStatus


class DeletionRequestCreate(BaseModel):
    target_kind: str = Field(pattern="^(student_file|analysis_run)$")
    target_id: UUID
    deletion_mode: DeletionMode = DeletionMode.SOFT_DELETE
    reason: str = Field(min_length=3)


class DeletionRequestRead(TimestampedReadModel):
    tenant_id: UUID
    requested_by_account_id: UUID
    target_kind: str
    target_id: UUID
    deletion_mode: DeletionMode
    status: DeletionRequestStatus
    reason: str
    scheduled_for: datetime | None
    processed_at: datetime | None
    metadata_json: dict[str, object]


class DeletionEventRead(TimestampedReadModel):
    deletion_request_id: UUID
    tenant_id: UUID
    target_kind: str
    target_id: UUID
    file_object_id: UUID | None
    action_kind: str
    message: str
    metadata_json: dict[str, object]


class PrivacyScanRead(TimestampedReadModel):
    tenant_id: UUID
    student_file_id: UUID | None
    student_artifact_id: UUID | None
    route_name: str
    masking_mode: PrivacyMaskingMode
    status: PrivacyScanStatus
    pii_detected: bool
    entity_count: int
    raw_text_sha256: str | None
    masked_preview: str | None
    findings_json: dict[str, object]
    metadata_json: dict[str, object]
