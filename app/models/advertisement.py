import uuid
import enum
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, UniqueConstraint, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

class AdvertisementStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PUBLISHED = "PUBLISHED"

class AdvertisementAction(str, enum.Enum):
    GENERATED = "GENERATED"
    EDITED = "EDITED"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PUBLISHED = "PUBLISHED"
    DELETED = "DELETED"

class Advertisement(Base):
    __tablename__ = "advertisements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id = Column(UUID(as_uuid=True), ForeignKey("vacancy_assessments.id"), nullable=False)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    academic_year = Column(String(20), nullable=False)
    
    vacancy_count = Column(Integer, nullable=False)
    qualification_requirements = Column(Text, nullable=True)
    required_documents = Column(Text, nullable=True)
    important_instructions = Column(Text, nullable=True)
    interview_venue = Column(String(255), nullable=True)
    content_en = Column(Text, nullable=False)
    content_mr = Column(Text, nullable=False)
    
    status = Column(String(30), default=AdvertisementStatus.DRAFT.value)
    rejection_reason = Column(Text, nullable=True)
    
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    
    application_start_date = Column(Date, nullable=True)
    application_end_date = Column(Date, nullable=True)
    
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('institution_id', 'course_id', 'academic_year', name='_adv_inst_course_year_uc'),
    )

    assessment = relationship("VacancyAssessment")
    audit_trail = relationship("AdvertisementAudit", back_populates="advertisement", cascade="all, delete-orphan")
    publication = relationship("PublishedAdvertisement", back_populates="advertisement", uselist=False)
