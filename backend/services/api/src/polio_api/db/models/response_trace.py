from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from polio_api.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ResponseTrace(Base):
    __tablename__ = "response_traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    diagnosis_run_id: Mapped[str] = mapped_column(ForeignKey("diagnosis_runs.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    model_name: Mapped[str] = mapped_column(String(120), default="grounded-fallback")
    request_excerpt: Mapped[str] = mapped_column(Text())
    response_excerpt: Mapped[str] = mapped_column(Text())
    trace_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    diagnosis_run: Mapped["DiagnosisRun"] = relationship(back_populates="response_traces")
    project: Mapped["Project"] = relationship(back_populates="response_traces")
    user: Mapped["User | None"] = relationship(back_populates="response_traces")
    citations: Mapped[list["Citation"]] = relationship(back_populates="response_trace", cascade="all, delete-orphan")
