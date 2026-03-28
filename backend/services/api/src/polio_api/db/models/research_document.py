from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from polio_api.core.database import Base
from polio_domain.enums import EvidenceProvenance


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ResearchDocument(Base):
    __tablename__ = "research_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    provenance_type: Mapped[str] = mapped_column(String(32), default=EvidenceProvenance.EXTERNAL_RESEARCH.value)
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    source_classification: Mapped[str] = mapped_column(String(32), index=True)
    trust_rank: Mapped[int] = mapped_column(default=0, index=True)
    title: Mapped[str] = mapped_column(String(500))
    canonical_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_on: Mapped[date | None] = mapped_column(Date(), nullable=True)
    usage_note: Mapped[str | None] = mapped_column(Text(), nullable=True)
    copyright_note: Mapped[str | None] = mapped_column(Text(), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    parser_name: Mapped[str] = mapped_column(String(80), default="research_pipeline")
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    last_error: Mapped[str | None] = mapped_column(Text(), nullable=True)
    content_text: Mapped[str] = mapped_column(Text(), default="")
    content_markdown: Mapped[str] = mapped_column(Text(), default="")
    author_names: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    chunk_count: Mapped[int] = mapped_column(default=0)
    word_count: Mapped[int] = mapped_column(default=0)
    ingested_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    project: Mapped["Project"] = relationship(back_populates="research_documents")
    chunks: Mapped[list["ResearchChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
