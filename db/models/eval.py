from __future__ import annotations

import uuid

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from db.types import JSONBType
from domain.enums import EvalExampleKind, LifecycleStatus


class EvalDatasetExample(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "eval_dataset_examples"
    __table_args__ = (
        UniqueConstraint("dataset_key", "example_key", name="uq_eval_dataset_examples_key"),
        Index("ix_eval_dataset_examples_kind_status", "example_kind", "status"),
    )

    dataset_key: Mapped[str] = mapped_column(String(120), nullable=False)
    example_key: Mapped[str] = mapped_column(String(120), nullable=False)
    example_kind: Mapped[EvalExampleKind] = mapped_column(Enum(EvalExampleKind, native_enum=False), nullable=False)
    status: Mapped[LifecycleStatus] = mapped_column(
        Enum(LifecycleStatus, native_enum=False),
        nullable=False,
        default=LifecycleStatus.ACTIVE,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    document_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_chunks_v2.id", ondelete="SET NULL"),
        nullable=True,
    )
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_claims_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)
    expected_flags_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    evidence_spans: Mapped[list["EvalEvidenceSpan"]] = relationship(back_populates="eval_example", cascade="all, delete-orphan")


class EvalEvidenceSpan(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "eval_evidence_spans"
    __table_args__ = (Index("ix_eval_evidence_spans_example_rank", "eval_example_id", "span_rank"),)

    eval_example_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("eval_dataset_examples.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_chunks_v2.id", ondelete="SET NULL"),
        nullable=True,
    )
    span_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quoted_text: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    eval_example: Mapped["EvalDatasetExample"] = relationship(back_populates="evidence_spans")


class RetrievalEvalCase(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "retrieval_eval_cases"
    __table_args__ = (
        UniqueConstraint("dataset_key", "case_key", name="uq_retrieval_eval_cases_key"),
        Index("ix_retrieval_eval_cases_dataset_status", "dataset_key", "status"),
    )

    dataset_key: Mapped[str] = mapped_column(String(120), nullable=False)
    case_key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[LifecycleStatus] = mapped_column(
        Enum(LifecycleStatus, native_enum=False),
        nullable=False,
        default=LifecycleStatus.ACTIVE,
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    filters_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)
    expected_results_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)
