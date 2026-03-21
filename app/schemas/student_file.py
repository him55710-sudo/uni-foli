from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.schemas.common import ORMModel, TimestampedReadModel
from domain.enums import PrivacyMaskingMode, StudentArtifactType, StudentFileStatus


class StudentArtifactRead(ORMModel):
    id: UUID
    artifact_type: StudentArtifactType
    artifact_index: int
    title: str | None
    section_label: str | None
    page_start: int | None
    page_end: int | None
    cleaned_text: str
    masked_text: str | None
    pii_detected: bool
    evidence_quality_score: float
    metadata_json: dict[str, object]


class StudentFileRead(TimestampedReadModel):
    tenant_id: UUID
    created_by_account_id: UUID | None
    owner_key: str
    file_object_id: UUID
    artifact_type: StudentArtifactType
    upload_filename: str
    mime_type: str
    language_code: str
    school_year_hint: int | None
    admissions_target_year: int | None
    privacy_masking_mode: PrivacyMaskingMode
    pii_detected: bool
    retention_expires_at: datetime | None
    deletion_requested_at: datetime | None
    purge_after_at: datetime | None
    status: StudentFileStatus
    parse_summary: dict[str, object]
    artifacts: list[StudentArtifactRead]
