from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from db.types import JSONBType
from domain.enums import PrivacyMaskingMode, StudentAnalysisRunStatus, StudentAnalysisRunType, StudentArtifactType, StudentFileStatus


class StudentFile(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "student_files"
    __table_args__ = (
        Index("ix_student_files_tenant_status", "tenant_id", "status"),
        Index("ix_student_files_file_object_id", "file_object_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    created_by_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    owner_key: Mapped[str] = mapped_column(String(120), nullable=False, default="local-dev")
    file_object_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("file_objects.id", ondelete="RESTRICT"), nullable=False)
    artifact_type: Mapped[StudentArtifactType] = mapped_column(
        Enum(StudentArtifactType, native_enum=False),
        nullable=False,
    )
    upload_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    language_code: Mapped[str] = mapped_column(String(12), nullable=False, default="ko")
    school_year_hint: Mapped[int | None] = mapped_column(Integer, nullable=True)
    admissions_target_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    privacy_masking_mode: Mapped[PrivacyMaskingMode] = mapped_column(
        Enum(PrivacyMaskingMode, native_enum=False),
        nullable=False,
        default=PrivacyMaskingMode.MASK_FOR_INDEX,
    )
    pii_detected: Mapped[bool] = mapped_column(nullable=False, default=False)
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purge_after_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[StudentFileStatus] = mapped_column(
        Enum(StudentFileStatus, native_enum=False),
        nullable=False,
        default=StudentFileStatus.UPLOADED,
    )
    parse_summary: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    tenant: Mapped["Tenant"] = relationship(back_populates="student_files")
    created_by_account: Mapped["Account | None"] = relationship(back_populates="created_student_files")
    file_object: Mapped["FileObject"] = relationship(back_populates="student_files")
    artifacts: Mapped[list["StudentArtifact"]] = relationship(back_populates="student_file", cascade="all, delete-orphan")
    analysis_runs: Mapped[list["StudentAnalysisRun"]] = relationship(back_populates="primary_student_file")


class StudentArtifact(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "student_artifacts"
    __table_args__ = (
        UniqueConstraint("student_file_id", "artifact_index", name="uq_student_artifacts_index"),
        Index("ix_student_artifacts_tenant_type", "tenant_id", "artifact_type"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    student_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("student_files.id", ondelete="CASCADE"), nullable=False)
    artifact_type: Mapped[StudentArtifactType] = mapped_column(
        Enum(StudentArtifactType, native_enum=False),
        nullable=False,
    )
    artifact_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    section_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_text: Mapped[str] = mapped_column(Text, nullable=False)
    masked_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    pii_detected: Mapped[bool] = mapped_column(nullable=False, default=False)
    evidence_quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    student_file: Mapped["StudentFile"] = relationship(back_populates="artifacts")
    citations: Mapped[list["Citation"]] = relationship(back_populates="student_artifact")


class StudentAnalysisRun(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "student_analysis_runs"
    __table_args__ = (Index("ix_student_analysis_runs_tenant_status", "tenant_id", "status"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    created_by_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    owner_key: Mapped[str] = mapped_column(String(120), nullable=False, default="local-dev")
    primary_student_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("student_files.id", ondelete="SET NULL"),
        nullable=True,
    )
    run_type: Mapped[StudentAnalysisRunType] = mapped_column(
        Enum(StudentAnalysisRunType, native_enum=False),
        nullable=False,
    )
    status: Mapped[StudentAnalysisRunStatus] = mapped_column(
        Enum(StudentAnalysisRunStatus, native_enum=False),
        nullable=False,
        default=StudentAnalysisRunStatus.QUEUED,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_template_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_snapshot: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)
    output_summary: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)
    analysis_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="analysis_runs")
    created_by_account: Mapped["Account | None"] = relationship(back_populates="created_analysis_runs")
    primary_student_file: Mapped["StudentFile | None"] = relationship(back_populates="analysis_runs")
    citations: Mapped[list["Citation"]] = relationship(back_populates="analysis_run")
    policy_flags: Mapped[list["PolicyFlag"]] = relationship(back_populates="student_analysis_run")
