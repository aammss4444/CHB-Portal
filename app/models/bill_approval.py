import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base
from app.models.chb_bill import BillApproverRole


class BillApprovalAction(str, enum.Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SENT_BACK = "SENT_BACK"


class BillApproval(Base):
    __tablename__ = "bill_approval"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bill_id = Column(UUID(as_uuid=True), ForeignKey("chb_bill.id"), nullable=False)
    approver_role = Column(
        Enum(BillApproverRole, name="chb_bill_approver_role_enum", create_type=False),
        nullable=False,
    )
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(Enum(BillApprovalAction, name="bill_approval_action_enum", create_type=False), nullable=False)
    remarks = Column(Text, nullable=True)
    actioned_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
