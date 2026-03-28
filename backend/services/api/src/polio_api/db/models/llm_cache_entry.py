from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from polio_api.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LLMCacheEntry(Base):
    __tablename__ = "llm_cache_entries"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    scope_key: Mapped[str] = mapped_column(String(255), index=True)
    feature_name: Mapped[str] = mapped_column(String(120), index=True)
    model_name: Mapped[str] = mapped_column(String(120))
    config_version: Mapped[str] = mapped_column(String(64))
    response_format: Mapped[str] = mapped_column(String(16), default="json")
    response_payload: Mapped[str] = mapped_column(Text())
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

