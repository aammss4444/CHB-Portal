import enum
import uuid
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class ApplicationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    SHORTLISTED = "SHORTLISTED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    advertisement_id = Column(UUID(as_uuid=True), ForeignKey("advertisements.id"), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=False)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    academic_year = Column(String(20), nullable=False)
    application_number = Column(String(50), nullable=False, unique=True)
    status = Column(String(30), nullable=False, default=ApplicationStatus.DRAFT.value)
    applied_designation = Column(String(100), nullable=True)
    cover_letter = Column(Text, nullable=True)
    declaration_accepted = Column(Boolean, nullable=False, default=False)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # AI Pipeline Metadata
    ai_status = Column(String(30), nullable=True) # COMPLETE, INCOMPLETE, REQUIRES_REVIEW
    ai_scrutiny_data = Column(Text, nullable=True) # Store serialized JSON summary
    ai_confidence_score = Column(Integer, nullable=True) # Score * 100
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("advertisement_id", "candidate_id", name="_app_ad_candidate_uc"),
    )

    candidate = relationship("Candidate", back_populates="applications")
    documents = relationship("ApplicationDocument", back_populates="application", cascade="all, delete-orphan")
