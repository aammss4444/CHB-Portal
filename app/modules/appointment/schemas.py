from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AppointmentApproveAction(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class AppointmentRespondAction(str, Enum):
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"


class AppointmentGenerateRequest(BaseModel):
    selection_result_id: UUID
    joining_date: date
    salary_per_lecture: Decimal = Field(..., gt=0)
    acceptance_deadline: date


class AppointmentUpdateRequest(BaseModel):
    joining_date: Optional[date] = None
    salary_per_lecture: Optional[Decimal] = Field(None, gt=0)
    acceptance_deadline: Optional[date] = None
    content_en: Optional[str] = None
    content_mr: Optional[str] = None


class AppointmentApproveRequest(BaseModel):
    action: AppointmentApproveAction
    remarks: Optional[str] = None


class AppointmentRespondRequest(BaseModel):
    action: AppointmentRespondAction
    remarks: Optional[str] = None


class AppointmentCancelRequest(BaseModel):
    remarks: str


class AppointmentAuditItem(BaseModel):
    action: str
    performed_by: Optional[int] = None
    remarks: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppointmentLetterResponse(BaseModel):
    id: UUID
    appointment_number: str
    selection_result_id: UUID
    candidate_id: UUID
    institution_id: int
    course_id: int
    academic_year: str
    designation: str
    joining_date: date
    salary_per_lecture: Decimal
    content_en: str
    content_mr: str
    file_path: Optional[str] = None
    download_url: Optional[str] = None
    status: str
    rejection_reason: Optional[str] = None
    generated_at: Optional[datetime] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    issued_at: Optional[datetime] = None
    issued_by: Optional[int] = None
    acceptance_deadline: Optional[date] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    audit_trail: list[AppointmentAuditItem] = []

    model_config = ConfigDict(from_attributes=True)


class AppointmentListItem(BaseModel):
    id: UUID
    appointment_number: str
    candidate_name: str
    status: str
    course: str
    joining_date: date
    credentials_issued: bool
    faculty_credential_id: Optional[UUID] = None


class AppointmentListResponse(BaseModel):
    total: int
    page: int
    size: int
    items: list[AppointmentListItem]


class CredentialResponse(BaseModel):
    faculty_code: str
    portal_username: str
    credential_issued_at: datetime
