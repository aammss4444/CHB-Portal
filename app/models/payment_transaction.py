import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base


class PaymentStatus(str, enum.Enum):
    INITIATED = "INITIATED"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class PaymentMode(str, enum.Enum):
    BANK_TRANSFER = "BANK_TRANSFER"
    UPI = "UPI"
    MANUAL = "MANUAL"


class PaymentTransaction(Base):
    __tablename__ = "payment_transaction"
    __table_args__ = (
        UniqueConstraint("bill_id", name="uq_payment_transaction_bill_id"),
        Index("ix_payment_transaction_payment_status", "payment_status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bill_id = Column(UUID(as_uuid=True), ForeignKey("chb_bill.id"), nullable=False, unique=True)
    faculty_credential_id = Column(UUID(as_uuid=True), ForeignKey("faculty_credentials.id"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    payment_status = Column(
        Enum(PaymentStatus, name="payment_status_enum", create_type=False),
        nullable=False,
        default=PaymentStatus.INITIATED.value,
    )
    payment_mode = Column(
        Enum(PaymentMode, name="payment_mode_enum", create_type=False),
        nullable=False,
        default=PaymentMode.BANK_TRANSFER.value,
    )
    transaction_reference = Column(String(255), nullable=True)
    bank_reference = Column(String(255), nullable=True)
    failure_reason = Column(Text, nullable=True)
    initiated_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
