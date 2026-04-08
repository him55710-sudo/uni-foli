from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from polio_api.core.database import Base, utc_now


class DiagnosisReportArtifact(Base):
    __tablename__ = "diagnosis_report_artifacts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    diagnosis_run_id = Column(String(36), ForeignKey("diagnosis_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    report_mode = Column(String(32), nullable=False, default="premium_10p")
    template_id = Column(String(80), nullable=True)
    export_format = Column(String(16), nullable=False, default="pdf")
    include_appendix = Column(Boolean, nullable=False, default=True)
    include_citations = Column(Boolean, nullable=False, default=True)
    status = Column(String(24), nullable=False, default="READY")
    version = Column(Integer, nullable=False, default=1)
    report_payload_json = Column(Text, nullable=False)
    generated_file_path = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    diagnosis_run = relationship("DiagnosisRun", back_populates="report_artifacts")
    project = relationship("Project", back_populates="diagnosis_report_artifacts", lazy="joined")
