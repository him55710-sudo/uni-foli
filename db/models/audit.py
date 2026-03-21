from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from db.types import JSONBType
from domain.enums import PolicyFlagCode, PolicyFlagStatus, ResponseTraceKind, ReviewTaskStatus, ReviewTaskType


class Citation(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "citations"
    __table_args__ = (Index("ix_citations_trace_kind", "response_trace_id", "citation_kind"),)

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    response_trace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("response_traces.id", ondelete="CASCADE"),
        nullable=True,
    )
    analysis_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("student_analysis_runs.id", ondelete="CASCADE"),
        nullable=True,
    )
    claim_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("claims.id", ondelete="SET NULL"), nullable=True)
    student_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("student_artifacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    citation_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    locator_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)
    quoted_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    response_trace: Mapped["ResponseTrace | None"] = relationship(back_populates="citations")
    analysis_run: Mapped["StudentAnalysisRun | None"] = relationship(back_populates="citations")
    claim: Mapped["Claim | None"] = relationship(back_populates="citations")
    student_artifact: Mapped["StudentArtifact | None"] = relationship(back_populates="citations")
    tenant: Mapped["Tenant | None"] = relationship(back_populates="citations")


class PolicyFlag(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "policy_flags"
    __table_args__ = (Index("ix_policy_flags_target_code", "target_kind", "flag_code"),)

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    student_analysis_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("student_analysis_runs.id", ondelete="CASCADE"),
        nullable=True,
    )
    target_kind: Mapped[str] = mapped_column(String(60), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    flag_code: Mapped[PolicyFlagCode] = mapped_column(Enum(PolicyFlagCode, native_enum=False), nullable=False)
    severity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[PolicyFlagStatus] = mapped_column(
        Enum(PolicyFlagStatus, native_enum=False),
        nullable=False,
        default=PolicyFlagStatus.OPEN,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    student_analysis_run: Mapped["StudentAnalysisRun | None"] = relationship(back_populates="policy_flags")
    tenant: Mapped["Tenant | None"] = relationship(back_populates="policy_flags")


class ReviewTask(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "review_tasks"
    __table_args__ = (Index("ix_review_tasks_type_status", "task_type", "status"),)

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    task_type: Mapped[ReviewTaskType] = mapped_column(Enum(ReviewTaskType, native_enum=False), nullable=False)
    status: Mapped[ReviewTaskStatus] = mapped_column(
        Enum(ReviewTaskStatus, native_enum=False),
        nullable=False,
        default=ReviewTaskStatus.OPEN,
    )
    target_kind: Mapped[str] = mapped_column(String(60), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(120), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    tenant: Mapped["Tenant | None"] = relationship(back_populates="review_tasks")


class ResponseTrace(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "response_traces"
    __table_args__ = (Index("ix_response_traces_kind_created_at", "response_kind", "created_at"),)

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    response_kind: Mapped[ResponseTraceKind] = mapped_column(
        Enum(ResponseTraceKind, native_enum=False),
        nullable=False,
    )
    owner_key: Mapped[str] = mapped_column(String(120), nullable=False, default="local-dev")
    route_name: Mapped[str] = mapped_column(String(120), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_template_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieval_trace: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)
    response_payload: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    citations: Mapped[list["Citation"]] = relationship(back_populates="response_trace", cascade="all, delete-orphan")
    tenant: Mapped["Tenant | None"] = relationship(back_populates="response_traces")
