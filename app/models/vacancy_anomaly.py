import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

class VacancyAnomaly(Base):
    __tablename__ = "vacancy_anomalies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id = Column(UUID(as_uuid=True), ForeignKey("vacancy_assessments.id"), nullable=True)
    advertisement_id = Column(UUID(as_uuid=True), ForeignKey("advertisements.id"), nullable=True)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False)
    faculty_id = Column(UUID(as_uuid=True), ForeignKey("existing_faculty.id"), nullable=True)
    
    anomaly_type = Column(String(100), nullable=False) # e.g., HIGH_VACANCY_RATIO
    severity = Column(String(20), nullable=False) # LOW, MEDIUM, HIGH
    description = Column(Text, nullable=False)
    
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    assessment = relationship("VacancyAssessment", back_populates="anomalies")
