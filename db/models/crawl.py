from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from db.types import JSONBType
from domain.enums import DiscoveredUrlStatus, LifecycleStatus, SourceSeedType


class SourceSeed(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "source_seeds"
    __table_args__ = (
        UniqueConstraint("source_id", "seed_url", name="uq_source_seeds_source_seed_url"),
        Index("ix_source_seeds_source_status", "source_id", "status"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    seed_type: Mapped[SourceSeedType] = mapped_column(Enum(SourceSeedType, native_enum=False), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    seed_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    allowed_domains: Mapped[list[str]] = mapped_column(JSONBType, nullable=False, default=list)
    allowed_path_prefixes: Mapped[list[str]] = mapped_column(JSONBType, nullable=False, default=list)
    denied_path_prefixes: Mapped[list[str]] = mapped_column(JSONBType, nullable=False, default=list)
    max_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    current_cycle_year_hint: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allow_binary_assets: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    respect_robots_txt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[LifecycleStatus] = mapped_column(
        Enum(LifecycleStatus, native_enum=False),
        nullable=False,
        default=LifecycleStatus.ACTIVE,
    )
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_succeeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    source: Mapped["Source"] = relationship(back_populates="source_seeds")
    crawl_jobs: Mapped[list["SourceCrawlJob"]] = relationship(back_populates="source_seed")
    discovered_urls: Mapped[list["DiscoveredUrl"]] = relationship(back_populates="source_seed")


class DiscoveredUrl(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "discovered_urls"
    __table_args__ = (
        UniqueConstraint("source_id", "canonical_url", name="uq_discovered_urls_source_canonical_url"),
        Index("ix_discovered_urls_seed_status", "source_seed_id", "status"),
        Index("ix_discovered_urls_source_refresh", "source_id", "next_refresh_at"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    source_seed_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_seeds.id", ondelete="CASCADE"), nullable=False)
    latest_crawl_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_crawl_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    file_object_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("file_objects.id", ondelete="SET NULL"), nullable=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    canonical_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    discovered_from_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_modified_header: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_html: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_downloadable_asset: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_current_cycle_relevant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[DiscoveredUrlStatus] = mapped_column(
        Enum(DiscoveredUrlStatus, native_enum=False),
        nullable=False,
        default=DiscoveredUrlStatus.DISCOVERED,
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    source: Mapped["Source"] = relationship(back_populates="discovered_urls")
    source_seed: Mapped["SourceSeed"] = relationship(back_populates="discovered_urls")
    latest_crawl_job: Mapped["SourceCrawlJob | None"] = relationship(back_populates="discovered_urls")
    file_object: Mapped["FileObject | None"] = relationship(back_populates="discovered_urls")
    document: Mapped["Document | None"] = relationship(back_populates="discovered_urls")
