from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from polio_api.core.database import Base, utc_now


class DiagnosisRun(Base):
    __tablename__ = "diagnosis_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), index=True, nullable=False)
    status = Column(String, nullable=False, default="PENDING")
    result_payload = Column(Text, nullable=True)  # JSON serialized DiagnosisResult
    status_message = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    project = relationship("Project", back_populates="diagnoses", lazy="joined")
    blueprints = relationship("Blueprint", back_populates="diagnosis_run", lazy="selectin")
    policy_flags = relationship("PolicyFlag", back_populates="diagnosis_run", lazy="selectin", cascade="all, delete-orphan")
    review_tasks = relationship("ReviewTask", back_populates="diagnosis_run", lazy="selectin", cascade="all, delete-orphan")
    response_traces = relationship("ResponseTrace", back_populates="diagnosis_run", lazy="selectin", cascade="all, delete-orphan")
