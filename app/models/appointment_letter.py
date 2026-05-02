import enum
import uuid
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class AppointmentLetterStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    ISSUED = "ISSUED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class AppointmentLetter(Base):
    __tablename__ = "appointment_letters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_number = Column(String(50), unique=True, nullable=False)
    selection_result_id = Column(UUID(as_uuid=True), ForeignKey("selection_results.id"), nullable=False, unique=True)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=False)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    academic_year = Column(String(20), nullable=False)
    designation = Column(String(100), nullable=False)
    joining_date = Column(Date, nullable=False)
    salary_per_lecture = Column(Numeric(10, 2), nullable=False)
    content_en = Column(Text, nullable=False)
    content_mr = Column(Text, nullable=False)
    file_path = Column(String(500), nullable=True)
    status = Column(String(30), nullable=False, default=AppointmentLetterStatus.DRAFT.value)
    rejection_reason = Column(Text, nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    issued_at = Column(DateTime(timezone=True), nullable=True)
    issued_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    acceptance_deadline = Column(Date, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("selection_result_id", name="_appointment_selection_result_uc"),
    )

    candidate = relationship("Candidate")
    selection_result = relationship("SelectionResult")
    audit_trail = relationship("AppointmentAudit", back_populates="appointment_letter")
