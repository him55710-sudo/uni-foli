from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from polio_api.core.database import Base
from polio_api.db.vector import DEFAULT_VECTOR_DIMENSIONS, EmbeddingVector
from polio_domain.enums import EvidenceProvenance


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ResearchChunk(Base):
    __tablename__ = "research_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_research_chunk_index"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("research_documents.id", ondelete="CASCADE"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    provenance_type: Mapped[str] = mapped_column(String(32), default=EvidenceProvenance.EXTERNAL_RESEARCH.value)
    chunk_index: Mapped[int] = mapped_column(Integer)
    char_start: Mapped[int] = mapped_column(Integer, default=0)
    char_end: Mapped[int] = mapped_column(Integer, default=0)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0)
    content_text: Mapped[str] = mapped_column(Text())
    embedding_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        EmbeddingVector(DEFAULT_VECTOR_DIMENSIONS),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    document: Mapped["ResearchDocument"] = relationship(back_populates="chunks")
    project: Mapped["Project"] = relationship(back_populates="research_chunks")
