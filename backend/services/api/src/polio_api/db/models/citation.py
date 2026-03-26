from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from polio_api.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    response_trace_id: Mapped[str] = mapped_column(ForeignKey("response_traces.id", ondelete="CASCADE"), index=True)
    diagnosis_run_id: Mapped[str] = mapped_column(ForeignKey("diagnosis_runs.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("parsed_documents.id", ondelete="SET NULL"), nullable=True)
    document_chunk_id: Mapped[str | None] = mapped_column(ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True)
    source_label: Mapped[str] = mapped_column(String(255))
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    excerpt: Mapped[str] = mapped_column(Text())
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    response_trace: Mapped["ResponseTrace"] = relationship(back_populates="citations")
    document: Mapped["ParsedDocument | None"] = relationship()
    document_chunk: Mapped["DocumentChunk | None"] = relationship()
