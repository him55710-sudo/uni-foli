from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from polio_api.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    target_university: Mapped[str | None] = mapped_column(String(200), nullable=True)
    target_major: Mapped[str | None] = mapped_column(String(200), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(50), nullable=True)
    track: Mapped[str | None] = mapped_column(String(100), nullable=True)
    career: Mapped[str | None] = mapped_column(String(200), nullable=True)
    admission_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    interest_universities: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    projects: Mapped[list["Project"]] = relationship(back_populates="owner")
    policy_flags: Mapped[list["PolicyFlag"]] = relationship(back_populates="user")
    review_tasks: Mapped[list["ReviewTask"]] = relationship(back_populates="user")
    response_traces: Mapped[list["ResponseTrace"]] = relationship(back_populates="user")
