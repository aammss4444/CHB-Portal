import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class CandidateQualification(Base):
    __tablename__ = "candidate_qualifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    degree = Column(String(100), nullable=False)
    specialization = Column(String(100), nullable=True)
    university = Column(String(255), nullable=True)
    year_of_passing = Column(Integer, nullable=True)
    percentage = Column(Numeric(5, 2), nullable=True)
    is_highest = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    candidate = relationship("Candidate", back_populates="qualifications")
