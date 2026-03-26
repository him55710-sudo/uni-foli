from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from polio_api.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReviewTask(Base):
    __tablename__ = "review_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    diagnosis_run_id: Mapped[str] = mapped_column(ForeignKey("diagnosis_runs.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    task_type: Mapped[str] = mapped_column(String(64), default="policy_review")
    status: Mapped[str] = mapped_column(String(24), default="open")
    assigned_role: Mapped[str] = mapped_column(String(32), default="admin")
    reason: Mapped[str] = mapped_column(Text())
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    diagnosis_run: Mapped["DiagnosisRun"] = relationship(back_populates="review_tasks")
    project: Mapped["Project"] = relationship(back_populates="review_tasks")
    user: Mapped["User | None"] = relationship(back_populates="review_tasks")
