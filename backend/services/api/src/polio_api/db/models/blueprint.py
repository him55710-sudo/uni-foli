from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from polio_api.core.database import Base

class Blueprint(Base):
    __tablename__ = "blueprints"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), index=True, nullable=False)
    diagnosis_run_id = Column(String, ForeignKey("diagnosis_runs.id"), nullable=True)
    headline = Column(String(500), nullable=True)
    recommended_focus = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="blueprints", lazy="joined")
    diagnosis_run = relationship("DiagnosisRun", back_populates="blueprints", lazy="joined")
    quests = relationship("Quest", back_populates="blueprint", cascade="all, delete-orphan", lazy="selectin")
