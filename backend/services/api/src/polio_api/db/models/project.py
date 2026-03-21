from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from polio_api.core.database import Base
from polio_domain.enums import ProjectStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    target_university: Mapped[str | None] = mapped_column(String(200), nullable=True)
    target_major: Mapped[str | None] = mapped_column(String(200), nullable=True)
    discussion_log: Mapped[str | None] = mapped_column(Text(), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=ProjectStatus.ACTIVE.value)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    uploads: Mapped[list["UploadAsset"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list["ParsedDocument"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    document_chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    drafts: Mapped[list["Draft"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    render_jobs: Mapped[list["RenderJob"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
