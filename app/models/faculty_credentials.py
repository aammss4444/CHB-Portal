import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.session import Base

class FacultyCredentials(Base):
    __tablename__ = "faculty_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_letter_id = Column(UUID(as_uuid=True), ForeignKey("appointment_letters.id"), nullable=True, unique=True)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=True)
    existing_faculty_id = Column(UUID(as_uuid=True), ForeignKey("existing_faculty.id"), nullable=True, unique=True)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    faculty_code = Column(String(50), nullable=False, unique=True)
    portal_username = Column(String(100), nullable=False, unique=True)
    temp_password_hash = Column(String, nullable=False)
    temp_password_plain = Column(String, nullable=True) # For dev display
    credential_issued_at = Column(DateTime(timezone=True), server_default=func.now())
    # STEP 7 GATE: faculty must have is_active = True credentials
    # before they can log attendance
    is_active = Column(Boolean, nullable=False, default=True)
    first_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    appointment_letter = relationship("AppointmentLetter")
    candidate = relationship("Candidate")
    user = relationship("User")
