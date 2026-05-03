import uuid
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    full_name = Column(String(255), nullable=False)
    father_name = Column(String(255), nullable=True)
    date_of_birth = Column(Date, nullable=True)

    gender = Column(String(20), nullable=True)
    category = Column(String(50), nullable=True)
    religion = Column(String(50), nullable=True)
    nationality = Column(String(50), nullable=False, default="Indian")
    mobile = Column(String(15), nullable=False)
    email = Column(String(255), nullable=False)
    address = Column(Text, nullable=True)
    district = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(10), nullable=True)
    aadhar_number = Column(String(128), nullable=True, unique=True)
    is_profile_complete = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    qualifications = relationship(
        "CandidateQualification",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )
    experiences = relationship(
        "CandidateExperience",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )
    applications = relationship("Application", back_populates="candidate")
