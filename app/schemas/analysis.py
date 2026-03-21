from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedReadModel
from domain.enums import StudentAnalysisRunStatus, StudentAnalysisRunType


class AnalysisRunCreate(BaseModel):
    run_type: StudentAnalysisRunType
    primary_student_file_id: str | None = None
    input_snapshot: dict[str, object] = Field(default_factory=dict)


class AnalysisRunRead(TimestampedReadModel):
    tenant_id: UUID
    created_by_account_id: UUID | None
    owner_key: str
    primary_student_file_id: UUID | None
    run_type: StudentAnalysisRunType
    status: StudentAnalysisRunStatus
    model_name: str | None
    prompt_template_key: str | None
    retention_expires_at: datetime | None
    deletion_requested_at: datetime | None
    input_snapshot: dict[str, object]
    output_summary: dict[str, object]
    analysis_notes: str | None
