from datetime import date, datetime
from enum import Enum
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.advertisement import AdvertisementStatus


class ApprovalDecision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class AdvertisementGenerateRequest(BaseModel):
    assessment_id: UUID
    application_start_date: date
    application_end_date: date
    qualification_requirements: Optional[str] = "As per AICTE/DTE norms"
    required_documents: Optional[str] = "- Degree Certificates\n- Mark Sheets\n- Experience Certificates\n- ID Proof"
    important_instructions: Optional[str] = "- Candidates must attend walk-in interview\n- Original documents required"
    interview_venue: Optional[str] = "Institution Campus"
    content_en: Optional[str] = None
    content_mr: Optional[str] = None

class AdvertisementUpdateRequest(BaseModel):
    content_en: str
    content_mr: str
    application_start_date: date
    application_end_date: date
    qualification_requirements: Optional[str] = None
    required_documents: Optional[str] = None
    important_instructions: Optional[str] = None
    interview_venue: Optional[str] = None


class AdvertisementApproveRequest(BaseModel):
    action: ApprovalDecision
    remarks: Optional[str] = None


class AdvertisementAuditResponse(BaseModel):
    id: UUID
    action: str
    performed_by: Optional[int]
    remarks: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdvertisementResponse(BaseModel):
    id: UUID
    assessment_id: UUID
    institution_id: int
    course_id: int
    academic_year: str
    vacancy_count: int
    qualification_requirements: Optional[str]
    required_documents: Optional[str]
    important_instructions: Optional[str]
    interview_venue: Optional[str]
    content_en: str
    content_mr: str
    status: AdvertisementStatus
    rejection_reason: Optional[str]
    application_start_date: Optional[date]
    application_end_date: Optional[date]
    created_at: datetime
    updated_at: datetime
    audit_trail: List[AdvertisementAuditResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PublicAdvertisementResponse(BaseModel):
    content_en: str
    content_mr: str
    institution_name: str
    course_name: str
    vacancy_count: int
    application_start_date: date
    application_end_date: date


class PublishResponse(BaseModel):
    public_token: str
    public_url: str


class AdvertisementEnvelope(BaseModel):
    status: Literal["success"] = "success"
    data: AdvertisementResponse
    warning: Optional[str] = None


class PublicAdvertisementEnvelope(BaseModel):
    status: Literal["success"] = "success"
    data: PublicAdvertisementResponse


class PublishEnvelope(BaseModel):
    status: Literal["success"] = "success"
    data: PublishResponse


from app.schemas.advertisement_ai import AdvertisementAIResponse
from app.schemas.advertisement_ai import AdvertisementAIRequest, AdvertisementMetaResponse

class AIAdvertisementGenerationResponse(BaseModel):
    template_ad: AdvertisementResponse
    ai_enhanced_ad: AdvertisementAIResponse

class AIAdvertisementGenerationEnvelope(BaseModel):
    status: Literal["success"] = "success"
    data: AIAdvertisementGenerationResponse

class PublishedAdvertisementItem(BaseModel):
    id: UUID
    institution_name: str
    course_name: str
    academic_year: str
    vacancy_count: int
    application_start_date: date
    application_end_date: date


class PublishedAdvertisementListEnvelope(BaseModel):
    status: Literal["success"] = "success"
    data: List[PublishedAdvertisementItem]


class AdvertisementMetaEnvelope(BaseModel):
    status: Literal["success"] = "success"
    data: AdvertisementMetaResponse


class AdvertisementAIGenerateData(BaseModel):
    template_ad: dict
    ai_generated_ad: AdvertisementAIResponse


class AdvertisementAIGenerateEnvelope(BaseModel):
    status: Literal["success"] = "success"
    data: AdvertisementAIGenerateData
