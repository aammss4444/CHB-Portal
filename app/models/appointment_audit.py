import enum
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class AppointmentAuditAction(str, enum.Enum):
    GENERATED = "GENERATED"
    EDITED = "EDITED"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ISSUED = "ISSUED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    CANCELLED = "CANCELLED"
    CREDENTIALS_ISSUED = "CREDENTIALS_ISSUED"


class AppointmentAudit(Base):
    __tablename__ = "appointment_audit"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_letter_id = Column(UUID(as_uuid=True), ForeignKey("appointment_letters.id"), nullable=False)
    action = Column(String(50), nullable=False)
    performed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    appointment_letter = relationship("AppointmentLetter", back_populates="audit_trail")
