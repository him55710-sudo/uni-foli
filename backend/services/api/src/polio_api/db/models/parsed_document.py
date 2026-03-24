from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from polio_api.core.database import Base
from polio_domain.enums import DocumentMaskingStatus, DocumentProcessingStatus


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
    parser_name: Mapped[str] = mapped_column(String(80), default="pending")
    source_extension: Mapped[str] = mapped_column(String(16), default=".pdf")
    status: Mapped[str] = mapped_column(String(32), default=DocumentProcessingStatus.UPLOADED.value)
    masking_status: Mapped[str] = mapped_column(String(32), default=DocumentMaskingStatus.PENDING.value)
    parse_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text(), nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    content_text: Mapped[str] = mapped_column(Text(), default="")
    content_markdown: Mapped[str] = mapped_column(Text(), default="")
    parse_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    parse_started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    parse_completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    project: Mapped["Project"] = relationship(back_populates="documents")
    upload_asset: Mapped["UploadAsset"] = relationship(back_populates="parsed_document")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
    drafts: Mapped[list["Draft"]] = relationship(back_populates="source_document")

    @property
    def original_filename(self) -> str | None:
        if self.upload_asset is None:
            return None
        return self.upload_asset.original_filename

    @property
    def content_type(self) -> str | None:
        if self.upload_asset is None:
            return None
        return self.upload_asset.content_type

    @property
    def file_size_bytes(self) -> int | None:
        if self.upload_asset is None:
            return None
        return self.upload_asset.file_size_bytes

    @property
    def sha256(self) -> str | None:
        if self.upload_asset is None:
            return None
        return self.upload_asset.sha256

    @property
    def stored_path(self) -> str | None:
        if self.upload_asset is None:
            return None
        return self.upload_asset.stored_path

    @property
    def upload_status(self) -> str | None:
        if self.upload_asset is None:
            return None
        return self.upload_asset.status

    @property
    def can_retry(self) -> bool:
        return self.status in {
            DocumentProcessingStatus.FAILED.value,
            DocumentProcessingStatus.PARTIAL.value,
        }
