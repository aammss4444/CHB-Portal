import uuid
from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base


class AppointmentAcceptance(Base):
    __tablename__ = "appointment_acceptances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_letter_id = Column(UUID(as_uuid=True), ForeignKey("appointment_letters.id"), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=False)
    action = Column(String(20), nullable=False)
    remarks = Column(Text, nullable=True)
    actioned_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
