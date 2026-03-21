from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from db.types import JSONBType
from domain.enums import CrawlJobStatus, CycleType, EvaluationDimensionCode, LifecycleStatus, SourceCategory, SourceTier


class Source(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_sources_slug"),
        Index("ix_sources_tier_status", "source_tier", "status"),
    )

    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    organization_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_tier: Mapped[SourceTier] = mapped_column(Enum(SourceTier, native_enum=False), nullable=False)
    source_category: Mapped[SourceCategory] = mapped_column(
        Enum(SourceCategory, native_enum=False),
        nullable=False,
        default=SourceCategory.OTHER,
    )
    base_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="KR")
    is_official: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_crawl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    freshness_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    status: Mapped[LifecycleStatus] = mapped_column(
        Enum(LifecycleStatus, native_enum=False),
        nullable=False,
        default=LifecycleStatus.ACTIVE,
    )
    crawl_policy: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    crawl_jobs: Mapped[list["SourceCrawlJob"]] = relationship(back_populates="source", cascade="all, delete-orphan")
    source_seeds: Mapped[list["SourceSeed"]] = relationship(back_populates="source", cascade="all, delete-orphan")
    discovered_urls: Mapped[list["DiscoveredUrl"]] = relationship(back_populates="source", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="source")


class SourceCrawlJob(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "source_crawl_jobs"
    __table_args__ = (Index("ix_source_crawl_jobs_source_status", "source_id", "status"),)

    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    source_seed_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_seeds.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[CrawlJobStatus] = mapped_column(
        Enum(CrawlJobStatus, native_enum=False),
        nullable=False,
        default=CrawlJobStatus.QUEUED,
    )
    trigger_mode: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    seed_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    crawl_scope: Mapped[str] = mapped_column(String(80), nullable=False, default="seed")
    discovered_url_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    downloaded_file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_stats: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    source: Mapped["Source"] = relationship(back_populates="crawl_jobs")
    source_seed: Mapped["SourceSeed | None"] = relationship(back_populates="crawl_jobs")
    discovered_urls: Mapped[list["DiscoveredUrl"]] = relationship(back_populates="latest_crawl_job")
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(back_populates="source_crawl_job")


class University(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "universities"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_universities_slug"),
        UniqueConstraint("official_code", name="uq_universities_official_code"),
    )

    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    official_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    name_ko: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    official_website: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    admissions_website: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[LifecycleStatus] = mapped_column(
        Enum(LifecycleStatus, native_enum=False),
        nullable=False,
        default=LifecycleStatus.ACTIVE,
    )
    aliases: Mapped[list[str]] = mapped_column(JSONBType, nullable=False, default=list)

    admission_cycles: Mapped[list["AdmissionCycle"]] = relationship(back_populates="university", cascade="all, delete-orphan")
    admission_tracks: Mapped[list["AdmissionTrack"]] = relationship(back_populates="university", cascade="all, delete-orphan")
    alias_rows: Mapped[list["UniversityAlias"]] = relationship(back_populates="university", cascade="all, delete-orphan")
    unit_alias_rows: Mapped[list["UniversityUnitAlias"]] = relationship(back_populates="university", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="university")


class AdmissionCycle(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "admission_cycles"
    __table_args__ = (
        UniqueConstraint("university_id", "admissions_year", "cycle_type", "label", name="uq_admission_cycles_scope"),
        Index("ix_admission_cycles_year_cycle_type", "admissions_year", "cycle_type"),
    )

    university_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("universities.id", ondelete="CASCADE"), nullable=False)
    admissions_year: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle_type: Mapped[CycleType] = mapped_column(Enum(CycleType, native_enum=False), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    started_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    ended_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current_cycle: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[LifecycleStatus] = mapped_column(
        Enum(LifecycleStatus, native_enum=False),
        nullable=False,
        default=LifecycleStatus.ACTIVE,
    )

    university: Mapped["University"] = relationship(back_populates="admission_cycles")
    admission_tracks: Mapped[list["AdmissionTrack"]] = relationship(back_populates="admission_cycle", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="admission_cycle")


class AdmissionTrack(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "admission_tracks"
    __table_args__ = (
        UniqueConstraint("admission_cycle_id", "track_name", "department_name", name="uq_admission_tracks_scope"),
        Index("ix_admission_tracks_cycle_track_name", "admission_cycle_id", "track_name"),
    )

    university_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("universities.id", ondelete="CASCADE"), nullable=False)
    admission_cycle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admission_cycles.id", ondelete="CASCADE"), nullable=False)
    track_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    track_name: Mapped[str] = mapped_column(String(255), nullable=False)
    college_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_student_record_focused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[LifecycleStatus] = mapped_column(
        Enum(LifecycleStatus, native_enum=False),
        nullable=False,
        default=LifecycleStatus.ACTIVE,
    )
    notes: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    university: Mapped["University"] = relationship(back_populates="admission_tracks")
    admission_cycle: Mapped["AdmissionCycle"] = relationship(back_populates="admission_tracks")
    documents: Mapped[list["Document"]] = relationship(back_populates="admission_track")


class EvaluationDimension(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "evaluation_dimensions"
    __table_args__ = (UniqueConstraint("code", name="uq_evaluation_dimensions_code"),)

    code: Mapped[EvaluationDimensionCode] = mapped_column(
        Enum(EvaluationDimensionCode, native_enum=False),
        nullable=False,
    )
    name_ko: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_global_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[LifecycleStatus] = mapped_column(
        Enum(LifecycleStatus, native_enum=False),
        nullable=False,
        default=LifecycleStatus.ACTIVE,
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    claims: Mapped[list["Claim"]] = relationship(back_populates="evaluation_dimension")
    aliases: Mapped[list["EvaluationDimensionAlias"]] = relationship(back_populates="evaluation_dimension", cascade="all, delete-orphan")
