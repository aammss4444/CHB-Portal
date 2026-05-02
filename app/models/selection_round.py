import uuid
import enum
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Date, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

class SelectionRoundType(str, enum.Enum):
    DOCUMENT_SCRUTINY = "DOCUMENT_SCRUTINY"
    INTERVIEW = "INTERVIEW"

class SelectionRoundStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"

class SelectionRound(Base):
    __tablename__ = "selection_rounds"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    advertisement_id = Column(UUID(as_uuid=True), ForeignKey("advertisements.id"), nullable=False)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    academic_year = Column(String(20), nullable=False)
    
    round_type = Column(String(50), nullable=False) # SelectionRoundType
    scheduled_date = Column(Date, nullable=False)
    status = Column(String(30), default=SelectionRoundStatus.SCHEDULED.value)
    
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('advertisement_id', 'round_type', name='_sel_round_type_uc'),
    )

    advertisement = relationship("Advertisement")
    shortlisted_candidates = relationship("ShortlistedCandidate", back_populates="round")
