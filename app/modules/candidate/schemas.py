from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class GenderEnum(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class CategoryEnum(str, Enum):
    OPEN = "OPEN"
    OBC = "OBC"
    SC = "SC"
    ST = "ST"
    EWS = "EWS"
    SBC = "SBC"
    VJNT = "VJNT"


class ExperienceTypeEnum(str, Enum):
    TEACHING = "TEACHING"
    INDUSTRY = "INDUSTRY"
    RESEARCH = "RESEARCH"


class CandidateProfileRequest(BaseModel):
    full_name: str
    father_name: Optional[str] = None
    date_of_birth: date
    gender: GenderEnum
    category: CategoryEnum
    religion: Optional[str] = None
    nationality: str = "Indian"
    mobile: str
    email: str
    address: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    aadhar_number: Optional[str] = None

    @field_validator("gender", mode="before")
    @classmethod
    def normalize_gender(cls, v):
        if isinstance(v, str):
            return v.upper()
        return v

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v):
        if isinstance(v, str):
            return v.upper()
        return v

    @field_validator("pincode", "aadhar_number", mode="before")
    @classmethod
    def coerce_to_string(cls, v):
        if v is not None and not isinstance(v, str):
            return str(v)
        return v


class QualificationInput(BaseModel):
    degree: str
    specialization: Optional[str] = None
    university: Optional[str] = None
    year_of_passing: Optional[int] = None
    percentage: Optional[Decimal] = None
    is_highest: bool = False


class QualificationBulkRequest(BaseModel):
    qualifications: List[QualificationInput]


class ExperienceInput(BaseModel):
    institution_name: Optional[str] = None
    designation: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    is_current: bool = False
    experience_type: ExperienceTypeEnum


class ExperienceBulkRequest(BaseModel):
    experiences: List[ExperienceInput]


class CandidateQualificationResponse(BaseModel):
    id: UUID
    degree: str
    specialization: Optional[str]
    university: Optional[str]
    year_of_passing: Optional[int]
    percentage: Optional[Decimal]
    is_highest: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CandidateExperienceResponse(BaseModel):
    id: UUID
    institution_name: Optional[str]
    designation: Optional[str]
    from_date: Optional[date]
    to_date: Optional[date]
    is_current: bool
    experience_type: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CandidateProfileResponse(BaseModel):
    id: UUID
    user_id: int
    full_name: str
    father_name: Optional[str]
    date_of_birth: Optional[date]
    gender: Optional[str]
    category: Optional[str]
    religion: Optional[str]
    nationality: str
    mobile: str
    email: str
    address: Optional[str]
    district: Optional[str]
    state: Optional[str]
    pincode: Optional[str]
    is_profile_complete: bool
    created_at: datetime
    updated_at: datetime
    qualifications: List[CandidateQualificationResponse]
    experiences: List[CandidateExperienceResponse]

    model_config = ConfigDict(from_attributes=True)


class Envelope(BaseModel):
    status: Literal["success"] = "success"
    data: dict
