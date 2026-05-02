import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

class VacancyAssessment(Base):
    __tablename__ = "vacancy_assessments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    academic_year = Column(String(20), nullable=False)
    requirement_id = Column(Integer, ForeignKey("faculty_requirements.id")) # FK to Step 1
    
    required_count = Column(Integer, nullable=False)
    total_existing = Column(Integer, nullable=False)
    effective_existing = Column(Integer, nullable=False)
    suggested_vacancy = Column(Integer, nullable=False)
    confirmed_vacancy = Column(Integer, nullable=True)
    
    status = Column(String(30), default="DRAFT") # DRAFT, AI_SUGGESTED, CONFIRMED
    ai_suggestion_notes = Column(Text, nullable=True)
    
    confirmed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('institution_id', 'course_id', 'academic_year', name='_inst_course_year_uc'),
    )

    anomalies = relationship("VacancyAnomaly", back_populates="assessment")
