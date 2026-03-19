from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from polio_api.core.database import Base
from polio_domain.enums import UploadStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UploadAsset(Base):
    __tablename__ = "upload_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(255), default="application/octet-stream")
    stored_path: Mapped[str] = mapped_column(String(500))
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=UploadStatus.STORED.value)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ingest_error: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    ingested_at: Mapped[datetime | None] = mapped_column(nullable=True)

    project: Mapped["Project"] = relationship(back_populates="uploads")
    parsed_document: Mapped["ParsedDocument | None"] = relationship(
        back_populates="upload_asset",
        cascade="all, delete-orphan",
        uselist=False,
    )
