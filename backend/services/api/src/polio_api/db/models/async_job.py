from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from polio_api.core.database import Base
from polio_domain.enums import AsyncJobStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AsyncJob(Base):
    __tablename__ = "async_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str] = mapped_column(String(64), index=True)
    resource_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default=AsyncJobStatus.QUEUED.value, index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=2)
    failure_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    failure_history: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dead_lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    project: Mapped["Project | None"] = relationship(back_populates="async_jobs")

    def schedule_retry(self, *, delay_seconds: int, reason: str) -> None:
        self.retry_count += 1
        self.failure_reason = reason
        self.failure_history = [
            *list(self.failure_history or []),
            {
                "attempt": self.retry_count,
                "failed_at": utc_now().isoformat(),
                "reason": reason,
            },
        ]
        self.status = AsyncJobStatus.RETRYING.value
        self.started_at = None
        self.completed_at = None
        self.next_attempt_at = utc_now() + timedelta(seconds=max(delay_seconds, 0))

