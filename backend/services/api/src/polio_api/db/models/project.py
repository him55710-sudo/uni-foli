from __future__ import annotations

from typing import TYPE_CHECKING
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from polio_api.core.database import Base
from polio_domain.enums import ProjectStatus

if TYPE_CHECKING:
    from polio_api.db.models.workshop import WorkshopSession
    from polio_api.db.models.user import User
    from polio_api.db.models.upload_asset import UploadAsset
    from polio_api.db.models.parsed_document import ParsedDocument
    from polio_api.db.models.document_chunk import DocumentChunk
    from polio_api.db.models.draft import Draft
    from polio_api.db.models.diagnosis_run import DiagnosisRun
    from polio_api.db.models.render_job import RenderJob
    from polio_api.db.models.blueprint import Blueprint
    from polio_api.db.models.policy_flag import PolicyFlag
    from polio_api.db.models.review_task import ReviewTask
    from polio_api.db.models.response_trace import ResponseTrace
    from polio_api.db.models.async_job import AsyncJob
    from polio_api.db.models.research_document import ResearchDocument
    from polio_api.db.models.research_chunk import ResearchChunk


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    target_university: Mapped[str | None] = mapped_column(String(200), nullable=True)
    target_major: Mapped[str | None] = mapped_column(String(200), nullable=True)
    discussion_log: Mapped[str | None] = mapped_column(Text(), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=ProjectStatus.ACTIVE.value)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    owner: Mapped["User | None"] = relationship(back_populates="projects")

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
    diagnoses: Mapped[list["DiagnosisRun"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    render_jobs: Mapped[list["RenderJob"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    blueprints: Mapped[list["Blueprint"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    policy_flags: Mapped[list["PolicyFlag"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    review_tasks: Mapped[list["ReviewTask"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    response_traces: Mapped[list["ResponseTrace"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    async_jobs: Mapped[list["AsyncJob"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    research_documents: Mapped[list["ResearchDocument"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    research_chunks: Mapped[list["ResearchChunk"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    workshop_sessions: Mapped[list["WorkshopSession"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
