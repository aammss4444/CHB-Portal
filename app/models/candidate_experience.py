import uuid
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class CandidateExperience(Base):
    __tablename__ = "candidate_experience"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    institution_name = Column(String(255), nullable=True)
    designation = Column(String(100), nullable=True)
    from_date = Column(Date, nullable=True)
    to_date = Column(Date, nullable=True)
    is_current = Column(Boolean, nullable=False, default=False)
    experience_type = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    candidate = relationship("Candidate", back_populates="experiences")
