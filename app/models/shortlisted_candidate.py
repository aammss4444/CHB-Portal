import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

class ShortlistedCandidate(Base):
    __tablename__ = "shortlisted_candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    advertisement_id = Column(UUID(as_uuid=True), ForeignKey("advertisements.id"), nullable=False)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=False)
    
    shortlisted_by = Column(Integer, ForeignKey("users.id"))
    shortlist_remarks = Column(Text, nullable=True)
    is_present = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('advertisement_id', 'application_id', name='_shortlist_ad_app_uc'),
    )

    application = relationship("Application")
    candidate = relationship("Candidate")
