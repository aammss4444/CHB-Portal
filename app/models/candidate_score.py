import uuid
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

class CandidateScore(Base):
    __tablename__ = "candidate_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    advertisement_id = Column(UUID(as_uuid=True), ForeignKey("advertisements.id"), nullable=False)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=False)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False)
    
    qualification_score = Column(Numeric(5, 2))
    experience_score = Column(Numeric(5, 2))
    interview_score = Column(Numeric(5, 2))
    publication_score = Column(Numeric(5, 2))
    reservation_tiebreaker = Column(Numeric(5, 2))
    
    final_score = Column(Numeric(5, 2))
    rank = Column(Integer)
    score_breakdown = Column(JSONB)
    
    computed_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('advertisement_id', 'application_id', name='_cand_score_ad_app_uc'),
    )

    application = relationship("Application")
    candidate = relationship("Candidate")
