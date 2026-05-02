import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base


class BillAuditAction(str, enum.Enum):
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SENT_BACK = "SENT_BACK"
    TREASURY_PROCESSED = "TREASURY_PROCESSED"
    REGENERATED = "REGENERATED"
    PAYMENT_INITIATED = "PAYMENT_INITIATED"
    PAYMENT_SUCCESS = "PAYMENT_SUCCESS"
    PAYMENT_FAILED = "PAYMENT_FAILED"


class BillAudit(Base):
    __tablename__ = "bill_audit"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bill_id = Column(UUID(as_uuid=True), ForeignKey("chb_bill.id"), nullable=False)
    action = Column(Enum(BillAuditAction, name="bill_audit_action_enum", create_type=False), nullable=False)
    performed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=True)
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
