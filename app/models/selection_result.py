import uuid
import enum
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

class SelectionResultStatus(str, enum.Enum):
    SELECTED = "SELECTED"
    WAITLISTED = "WAITLISTED"
    REJECTED = "REJECTED"

class FinalResultStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"

class SelectionResult(Base):
    __tablename__ = "selection_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    advertisement_id = Column(UUID(as_uuid=True), ForeignKey("advertisements.id"), nullable=False)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=False)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    academic_year = Column(String(20), nullable=False)
    
    rank = Column(Integer, nullable=False)
    final_score = Column(Numeric(5, 2), nullable=False)
    result_status = Column(String(30), nullable=False) # SelectionResultStatus
    waitlist_position = Column(Integer, nullable=True)
    
    confirmed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(30), default=FinalResultStatus.DRAFT.value)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('advertisement_id', 'candidate_id', name='_sel_result_ad_cand_uc'),
    )

    application = relationship("Application")
