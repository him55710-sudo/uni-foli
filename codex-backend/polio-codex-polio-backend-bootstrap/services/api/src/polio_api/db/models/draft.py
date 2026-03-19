from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from polio_api.core.database import Base
from polio_domain.enums import DraftStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    source_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("parsed_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(200))
    content_markdown: Mapped[str] = mapped_column(Text(), default="")
    status: Mapped[str] = mapped_column(String(32), default=DraftStatus.IN_PROGRESS.value)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    project: Mapped["Project"] = relationship(back_populates="drafts")
    source_document: Mapped["ParsedDocument | None"] = relationship(back_populates="drafts")
    render_jobs: Mapped[list["RenderJob"]] = relationship(back_populates="draft")
