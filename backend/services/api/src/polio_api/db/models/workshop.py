from __future__ import annotations

from typing import TYPE_CHECKING
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from polio_api.core.database import Base
from polio_domain.enums import WorkshopStatus, TurnType, QualityLevel

if TYPE_CHECKING:
    from polio_api.db.models.project import Project


json_type = JSON().with_variant(JSONB, "postgresql")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WorkshopSession(Base):
    __tablename__ = "workshop_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    quest_id: Mapped[str | None] = mapped_column(String, ForeignKey("quests.id"), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=WorkshopStatus.IDLE.value)
    context_score: Mapped[int] = mapped_column(Integer, default=0)
    quality_level: Mapped[str] = mapped_column(String(8), default=QualityLevel.MID.value)  # low/mid/high
    stream_token: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True, index=True)
    stream_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="workshop_sessions")
    turns: Mapped[list["WorkshopTurn"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="WorkshopTurn.created_at"
    )
    pinned_references: Mapped[list["PinnedReference"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan"
    )
    draft_artifacts: Mapped[list["DraftArtifact"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="DraftArtifact.created_at"
    )

class WorkshopTurn(Base):
    __tablename__ = "workshop_turns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("workshop_sessions.id"), index=True, nullable=False)
    turn_type: Mapped[str] = mapped_column(String(32), default=TurnType.MESSAGE.value)  # starter, follow_up, message
    query: Mapped[str] = mapped_column(Text(), nullable=False)
    response: Mapped[str | None] = mapped_column(Text(), nullable=True)
    action_payload: Mapped[dict | None] = mapped_column(json_type, nullable=True)  # Store structured choice info
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    session: Mapped["WorkshopSession"] = relationship(back_populates="turns")

class PinnedReference(Base):
    __tablename__ = "pinned_references"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("workshop_sessions.id"), index=True, nullable=False)
    text_content: Mapped[str] = mapped_column(Text(), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    session: Mapped["WorkshopSession"] = relationship(back_populates="pinned_references")


class DraftArtifact(Base):
    """워크샵 렌더링 결과물 - Polio 핵심 산출물"""
    __tablename__ = "draft_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("workshop_sessions.id"), index=True, nullable=False)

    # 핵심 산출물 필드
    report_markdown: Mapped[str | None] = mapped_column(Text(), nullable=True)           # 탐구 보고서 본문
    teacher_record_summary_500: Mapped[str | None] = mapped_column(Text(), nullable=True)  # 세특 500자 요약
    student_submission_note: Mapped[str | None] = mapped_column(Text(), nullable=True)   # 학생 제출용 노트
    evidence_map: Mapped[dict | None] = mapped_column(json_type, nullable=True)              # 증거 맵 (설명 가능성)
    visual_specs: Mapped[list[dict]] = mapped_column(json_type, default=list, nullable=False)
    math_expressions: Mapped[list[dict]] = mapped_column(json_type, default=list, nullable=False)

    render_status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/streaming/completed/failed
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)

    # 안전성/품질 메타데이터
    quality_level_applied: Mapped[str | None] = mapped_column(String(8), nullable=True)   # 실제 적용된 수준
    safety_score: Mapped[int | None] = mapped_column(Integer, nullable=True)               # 0~100 (높을수록 안전)
    safety_flags: Mapped[dict | None] = mapped_column(json_type, nullable=True)                # 위험 항목 상세
    quality_downgraded: Mapped[bool] = mapped_column(Boolean, default=False)               # 강등 여부
    quality_control_meta: Mapped[dict | None] = mapped_column(json_type, nullable=True)    # 품질/안전 메타데이터

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    session: Mapped["WorkshopSession"] = relationship(back_populates="draft_artifacts")
