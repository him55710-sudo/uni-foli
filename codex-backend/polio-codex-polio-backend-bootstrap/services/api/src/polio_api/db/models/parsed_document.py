from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from polio_api.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ParsedDocument(Base):
    __tablename__ = "parsed_documents"
    __table_args__ = (
        UniqueConstraint("upload_asset_id", name="uq_parsed_documents_upload_asset_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    upload_asset_id: Mapped[str] = mapped_column(ForeignKey("upload_assets.id", ondelete="CASCADE"))
    parser_name: Mapped[str] = mapped_column(String(80), default="pypdf")
    source_extension: Mapped[str] = mapped_column(String(16), default=".pdf")
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    content_text: Mapped[str] = mapped_column(Text(), default="")
    content_markdown: Mapped[str] = mapped_column(Text(), default="")
    parse_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    project: Mapped["Project"] = relationship(back_populates="documents")
    upload_asset: Mapped["UploadAsset"] = relationship(back_populates="parsed_document")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
    drafts: Mapped[list["Draft"]] = relationship(back_populates="source_document")
