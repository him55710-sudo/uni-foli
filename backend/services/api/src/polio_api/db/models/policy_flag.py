from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from polio_api.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PolicyFlag(Base):
    __tablename__ = "policy_flags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    diagnosis_run_id: Mapped[str] = mapped_column(ForeignKey("diagnosis_runs.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    code: Mapped[str] = mapped_column(String(80))
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    detail: Mapped[str] = mapped_column(Text())
    matched_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    match_count: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="open")
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    diagnosis_run: Mapped["DiagnosisRun"] = relationship(back_populates="policy_flags")
    project: Mapped["Project"] = relationship(back_populates="policy_flags")
    user: Mapped["User | None"] = relationship(back_populates="policy_flags")
