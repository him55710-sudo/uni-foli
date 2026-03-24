from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from polio_api.core.database import Base

class Quest(Base):
    __tablename__ = "quests"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    blueprint_id = Column(String, ForeignKey("blueprints.id"), index=True, nullable=False)
    
    subject = Column(String, nullable=False)
    title = Column(String, nullable=False)
    summary = Column(String, nullable=False)
    difficulty = Column(String, nullable=False)  # low, medium, high
    why_this_matters = Column(String, nullable=False)
    expected_record_impact = Column(String, nullable=False)
    recommended_output_type = Column(String, nullable=False)
    
    status = Column(String, nullable=False, default="PENDING")  # PENDING, IN_PROGRESS, COMPLETED
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    blueprint = relationship("Blueprint", back_populates="quests", lazy="joined")
