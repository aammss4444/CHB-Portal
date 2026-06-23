from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

class FacultyRequirement(Base):
    __tablename__ = "faculty_requirements"

    id = Column(Integer, primary_key=True, index=True)
    intake_id = Column(Integer, ForeignKey("intake_definitions.id", ondelete="CASCADE"), nullable=False)
    computed_required_count = Column(Integer, nullable=False)
    formula_breakdown = Column(JSONB, nullable=False) # Stores calculation details
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    intake = relationship("IntakeDefinition", back_populates="faculty_requirements")
    anomalies = relationship("RequirementAnomaly", back_populates="requirement", cascade="all, delete-orphan", passive_deletes=True)

class RequirementAnomaly(Base):
    __tablename__ = "requirement_anomalies"

    id = Column(Integer, primary_key=True, index=True)
    requirement_id = Column(Integer, ForeignKey("faculty_requirements.id", ondelete="CASCADE"), nullable=False)
    severity = Column(String, nullable=False) # e.g., LOW, HIGH, CRITICAL
    description = Column(String, nullable=False)
    is_acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    requirement = relationship("FacultyRequirement", back_populates="anomalies")
