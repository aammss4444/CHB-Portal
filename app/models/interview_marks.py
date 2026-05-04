import uuid
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Boolean, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

class InterviewMarks(Base):
    __tablename__ = "interview_marks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    advertisement_id = Column(UUID(as_uuid=True), ForeignKey("advertisements.id"), nullable=False)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=False)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False)
    
    subject_knowledge = Column(Numeric(5, 2), nullable=False)
    teaching_aptitude = Column(Numeric(5, 2), nullable=False)
    communication_skills = Column(Numeric(5, 2), nullable=False)
    overall_impression = Column(Numeric(5, 2), nullable=False)
    
    interview_total = Column(Numeric(5, 2), nullable=True) # Average of above 4
    
    entered_by = Column(Integer, ForeignKey("users.id"))
    entered_at = Column(DateTime(timezone=True), server_default=func.now())
    is_locked = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint('advertisement_id', 'application_id', name='_int_marks_ad_app_uc'),
    )

    application = relationship("Application")
