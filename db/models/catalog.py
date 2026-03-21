from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from db.types import JSONBType
from domain.enums import DocumentType, LifecycleStatus, SourceTier


class UniversityAlias(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "university_aliases"
    __table_args__ = (
        UniqueConstraint("alias_text", name="uq_university_aliases_alias_text"),
        Index("ix_university_aliases_university_status", "university_id", "status"),
    )

    university_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("universities.id", ondelete="CASCADE"), nullable=False)
    alias_text: Mapped[str] = mapped_column(String(255), nullable=False)
    alias_kind: Mapped[str] = mapped_column(String(60), nullable=False, default="name")
    campus_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_official: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[LifecycleStatus] = mapped_column(
        Enum(LifecycleStatus, native_enum=False),
        nullable=False,
        default=LifecycleStatus.ACTIVE,
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    university: Mapped["University"] = relationship(back_populates="alias_rows")


class UniversityUnitAlias(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "university_unit_aliases"
    __table_args__ = (
        UniqueConstraint("university_id", "source_text", name="uq_university_unit_aliases_source_text"),
        Index("ix_university_unit_aliases_university_status", "university_id", "status"),
    )

    university_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("universities.id", ondelete="CASCADE"), nullable=False)
    source_text: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_unit_name: Mapped[str] = mapped_column(String(255), nullable=False)
    campus_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    college_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[LifecycleStatus] = mapped_column(
        Enum(LifecycleStatus, native_enum=False),
        nullable=False,
        default=LifecycleStatus.ACTIVE,
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    university: Mapped["University"] = relationship(back_populates="unit_alias_rows")


class AdmissionCycleAlias(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "admission_cycle_aliases"
    __table_args__ = (UniqueConstraint("alias_text", name="uq_admission_cycle_aliases_alias_text"),)

    alias_text: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_label: Mapped[str] = mapped_column(String(80), nullable=False)
    cycle_type: Mapped[str] = mapped_column(String(40), nullable=False)
    admissions_year_hint: Mapped[int | None] = mapped_column(nullable=True)
    is_current_cycle_hint: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)


class EvaluationDimensionAlias(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "evaluation_dimension_aliases"
    __table_args__ = (UniqueConstraint("alias_text", name="uq_evaluation_dimension_aliases_alias_text"),)

    evaluation_dimension_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_dimensions.id", ondelete="CASCADE"),
        nullable=False,
    )
    alias_text: Mapped[str] = mapped_column(String(255), nullable=False)
    language_code: Mapped[str] = mapped_column(String(8), nullable=False, default="ko")
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    evaluation_dimension: Mapped["EvaluationDimension"] = relationship(back_populates="aliases")


class DocumentTypeLabel(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "document_type_labels"
    __table_args__ = (UniqueConstraint("label_text", "language_code", name="uq_document_type_labels_label_language"),)

    label_text: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType, native_enum=False), nullable=False)
    language_code: Mapped[str] = mapped_column(String(8), nullable=False, default="ko")
    match_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="contains")
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)


class SourceTierExample(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "source_tier_examples"
    __table_args__ = (
        UniqueConstraint("example_text", name="uq_source_tier_examples_example_text"),
        Index("ix_source_tier_examples_tier", "source_tier"),
    )

    source_tier: Mapped[SourceTier] = mapped_column(Enum(SourceTier, native_enum=False), nullable=False)
    example_text: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    is_positive_example: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)
