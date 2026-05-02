import enum
import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base


class BillStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    PRINCIPAL_APPROVED = "PRINCIPAL_APPROVED"
    RO_APPROVED = "RO_APPROVED"
    DIRECTORATE_APPROVED = "DIRECTORATE_APPROVED"
    TREASURY_PROCESSED = "TREASURY_PROCESSED"
    REJECTED = "REJECTED"


class BillApproverRole(str, enum.Enum):
    PRINCIPAL = "PRINCIPAL"
    RO = "RO"
    DIRECTORATE = "DIRECTORATE"
    TREASURY = "TREASURY"


class CHBBill(Base):
    __tablename__ = "chb_bill"
    __table_args__ = (
        UniqueConstraint("bill_number", name="uq_chb_bill_bill_number"),
        UniqueConstraint(
            "faculty_credential_id",
            "period_start",
            "period_end",
            name="uq_chb_bill_faculty_period",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bill_number = Column(String(50), nullable=False, unique=True)
    faculty_credential_id = Column(UUID(as_uuid=True), ForeignKey("faculty_credentials.id"), nullable=False)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    academic_year = Column(String(20), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    designation = Column(String(100), nullable=False)
    total_theory_lectures = Column(Integer, nullable=False, default=0)
    total_lab_lectures = Column(Integer, nullable=False, default=0)
    total_tutorial_lectures = Column(Integer, nullable=False, default=0)
    total_extra_lectures = Column(Integer, nullable=False, default=0)
    total_substitute_lectures = Column(Integer, nullable=False, default=0)
    total_billable_lectures = Column(Integer, nullable=False)
    gross_amount = Column(Numeric(12, 2), nullable=False)
    deductions = Column(Numeric(12, 2), nullable=False, default=0)
    net_amount = Column(Numeric(12, 2), nullable=False)
    bill_status = Column(Enum(BillStatus, name="chb_bill_status_enum", create_type=False), nullable=False, default=BillStatus.DRAFT.value)
    current_approver_role = Column(
        Enum(BillApproverRole, name="chb_bill_approver_role_enum", create_type=False),
        nullable=True,
    )
    rejection_stage = Column(String(50), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    generated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    treasury_processed_at = Column(DateTime(timezone=True), nullable=True)
    is_locked = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
