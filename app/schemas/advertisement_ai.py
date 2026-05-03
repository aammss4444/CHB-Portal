from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class AIComplianceFlag(BaseModel):
    type: str
    severity: str
    message: str


class AdvertisementAIRequest(BaseModel):
    institution_id: int
    course_id: int
    vacancy_count: int
    deadline: str
    application_mode: Optional[str] = "Walk-in"
    academic_year: Optional[str] = "2026-27"


class AdvertisementAIResponse(BaseModel):
    english: str
    marathi: str
    issues: List[str]
    confidence_score: float
    sections_present: Dict[str, bool] = Field(default_factory=dict)


class AdvertisementMetaInstitution(BaseModel):
    id: int
    name: str


class AdvertisementMetaCourse(BaseModel):
    id: int
    name: str
    level: str


class AdvertisementMetaNorms(BaseModel):
    min_qualification: Optional[str] = None
    faculty_student_ratio: Optional[float] = None


class AdvertisementMetaResponse(BaseModel):
    institutions: List[AdvertisementMetaInstitution]
    courses: List[AdvertisementMetaCourse]
    norms: AdvertisementMetaNorms
    reservation: Dict[str, int]
    suggested_vacancy: Optional[int] = None
