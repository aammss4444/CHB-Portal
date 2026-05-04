from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from app.models.rate_master import CHBDesignation, RateLectureType


class RateCreateItem(BaseModel):
    designation: CHBDesignation
    lecture_type: RateLectureType
    rate_per_lecture: Decimal = Field(..., gt=0)
    effective_from: date
    effective_to: Optional[date] = None
    is_active: bool = True


class RateMasterCreateRequest(BaseModel):
    institution_id: int
    academic_year: str
    rates: list[RateCreateItem]


class RateMasterUpdateRequest(BaseModel):
    rate_per_lecture: Optional[Decimal] = Field(None, gt=0)
    effective_to: Optional[date] = None
    is_active: Optional[bool] = None


class BillGenerateRequest(BaseModel):
    faculty_credential_id: UUID
    period_start: date
    period_end: date
    academic_year: str


class BulkBillGenerateRequest(BaseModel):
    institution_id: int
    period_start: date
    period_end: date
    academic_year: str


class BillApprovalActionRequest(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class BillApprovalRequest(BaseModel):
    action: BillApprovalActionRequest
    remarks: Optional[str] = None


class BillSubmitRequest(BaseModel):
    pass


class RateMasterResponse(BaseModel):
    id: UUID
    institution_id: int
    academic_year: str
    designation: str
    lecture_type: str
    rate_per_lecture: Decimal
    effective_from: date
    effective_to: Optional[date] = None
    is_active: bool
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BillLineItemResponse(BaseModel):
    id: UUID
    bill_id: UUID
    lecture_log_id: UUID
    lecture_date: date
    slot_number: int
    subject_name: str
    lecture_type: str
    class_name: Optional[str] = None
    rate_per_lecture: Decimal
    amount: Decimal
    is_extra: bool
    is_substitute: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BillApprovalResponse(BaseModel):
    approver_role: str
    action: str
    remarks: Optional[str] = None
    actioned_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttendanceAnomalyFlag(BaseModel):
    id: UUID
    anomaly_type: str
    severity: str
    description: str
    is_acknowledged: bool
    created_at: datetime


class CHBBillSummaryResponse(BaseModel):
    id: UUID
    bill_number: str
    faculty_credential_id: UUID
    institution_id: int
    course_id: int
    academic_year: str
    period_start: date
    period_end: date
    designation: str
    total_theory_lectures: int
    total_lab_lectures: int
    total_tutorial_lectures: int
    total_extra_lectures: int
    total_substitute_lectures: int
    total_billable_lectures: int
    gross_amount: Decimal
    deductions: Decimal
    net_amount: Decimal
    bill_status: str
    current_approver_role: Optional[str] = None
    rejection_stage: Optional[str] = None
    rejection_reason: Optional[str] = None
    generated_by: Optional[int] = None
    generated_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    treasury_processed_at: Optional[datetime] = None
    is_locked: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CHBBillResponse(CHBBillSummaryResponse):
    # STEP 9 GATE: net_amount from this response is the disbursable amount
    line_items: list[BillLineItemResponse] = Field(default_factory=list)
    approval_chain: list[BillApprovalResponse] = Field(default_factory=list)
    anomaly_flags: list[AttendanceAnomalyFlag] = Field(default_factory=list)


class BulkSkippedItem(BaseModel):
    faculty_credential_id: UUID
    reason: str


class BulkGenerateResponse(BaseModel):
    success_count: int
    skipped: list[BulkSkippedItem]


class InstitutionBillSummaryResponse(BaseModel):
    total_bills_generated: int
    total_gross_amount: Decimal
    total_net_amount: Decimal
    bills_pending_principal: int
    bills_pending_ro: int
    bills_pending_directorate: int
    bills_pending_treasury: int
    bills_rejected: int
    bills_processed: int
