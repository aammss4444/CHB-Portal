from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.application import ApplicationStatus
from app.schemas.document_ai import DocumentAIResponse


class DocumentTypeEnum(str, Enum):
    PHOTO = "PHOTO"
    SIGNATURE = "SIGNATURE"
    AADHAR = "AADHAR"
    PAN = "PAN"
    DEGREE_CERTIFICATE = "DEGREE_CERTIFICATE"
    MARKSHEET = "MARKSHEET"
    EXPERIENCE_LETTER = "EXPERIENCE_LETTER"
    CASTE_CERTIFICATE = "CASTE_CERTIFICATE"
    NOC = "NOC"
    PUBLICATION_PROOF = "PUBLICATION_PROOF"
    OTHER = "OTHER"


class ApplicationCreateRequest(BaseModel):
    advertisement_id: UUID
    applied_designation: Optional[str] = "Lecturer (CHB)"
    cover_letter: Optional[str] = None


class ApplicationSubmitRequest(BaseModel):
    declaration_accepted: bool


class ApplicationAction(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    UNDER_REVIEW = "UNDER_REVIEW"


class ApplicationActionRequest(BaseModel):
    action: ApplicationAction
    remarks: Optional[str] = None


class ApplicationDocumentResponse(BaseModel):
    id: UUID
    document_type: str
    file_name: str
    file_path: str
    file_size_kb: Optional[int]
    mime_type: Optional[str]
    validation_status: str
    validation_message: Optional[str]
    uploaded_at: datetime
    validated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ApplicationResponse(BaseModel):
    id: UUID
    advertisement_id: UUID
    candidate_id: UUID
    institution_id: int
    course_id: int
    academic_year: str
    application_number: str
    status: ApplicationStatus
    applied_designation: Optional[str]
    declaration_accepted: bool
    submitted_at: Optional[datetime]
    reviewed_at: Optional[datetime]
    rejection_reason: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApplicationSubmitResponse(BaseModel):
    application_number: str
    submitted_at: datetime
    status: ApplicationStatus


class MyApplicationItem(BaseModel):
    application_id: UUID
    application_number: str
    status: str
    institution_name: str
    course_name: str
    academic_year: str
    advertisement_name: str


class AdminApplicationItem(BaseModel):
    application_id: UUID
    application_number: str
    status: str
    candidate_name: str
    institution_name: str
    course_name: str
    academic_year: str
    invalid_documents: int
    suspicious_documents: int
    pending_documents: int
    valid_documents: int


class ApplicationAISummaryData(BaseModel):
    id: UUID
    ai_status: Optional[str]
    scrutiny_summary: str
    issues: list[str]
    confidence_score: float


class ApplicationAISummaryEnvelope(BaseModel):
    status: str
    data: ApplicationAISummaryData


class ApplicationAIAnalyzeData(DocumentAIResponse):
    classification: str


class ApplicationAIAnalyzeEnvelope(BaseModel):
    status: str
    data: ApplicationAIAnalyzeData
