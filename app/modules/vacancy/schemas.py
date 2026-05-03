from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import date, datetime
from uuid import UUID


# --- Faculty Qualifications ---
class QualificationBase(BaseModel):
    degree: str
    specialization: Optional[str] = None
    university: Optional[str] = None
    year_of_passing: Optional[int] = None
    is_highest: bool = False


class QualificationCreate(QualificationBase):
    pass


class QualificationResponse(QualificationBase):
    id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Existing Faculty ---
class FacultyBase(BaseModel):
    full_name: str
    designation: str  # Professor, Associate Professor, Assistant Professor
    employment_type: str  # PERMANENT, CONTRACT, DEPUTED_IN
    qualification: Optional[str] = None
    specialization: Optional[str] = None
    date_of_birth: Optional[date] = None
    date_of_joining: date
    status: str = "ACTIVE"  # ACTIVE, ON_LEAVE, DEPUTED_OUT, RETIRED
    academic_year: str


class FacultyCreateRequest(FacultyBase):
    institution_id: int
    course_id: int
    employee_id: str
    qualifications: List[QualificationCreate] = []


class FacultyUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    designation: Optional[str] = None
    employment_type: Optional[str] = None
    qualification: Optional[str] = None
    specialization: Optional[str] = None
    status: Optional[str] = None
    date_of_birth: Optional[date] = None
    date_of_joining: Optional[date] = None
    academic_year: Optional[str] = None
    qualifications: Optional[List[QualificationCreate]] = None


class FacultyResponse(FacultyBase):
    id: UUID
    institution_id: int
    course_id: int
    employee_id: str
    is_effective: bool
    qualifications_list: List[QualificationResponse] = []
    model_config = ConfigDict(from_attributes=True)


class FacultyListResponse(BaseModel):
    items: List[FacultyResponse]
    total_count: int
    effective_count: int
    non_effective_count: int


# --- Vacancy Assessment ---
class VacancyAssessmentBase(BaseModel):
    institution_id: int
    course_id: int
    academic_year: str


class VacancySuggestRequest(VacancyAssessmentBase):
    pass


class AnomalyResponse(BaseModel):
    id: UUID
    anomaly_type: str
    severity: str
    description: str
    is_acknowledged: bool
    model_config = ConfigDict(from_attributes=True)


class VacancyAssessmentResponse(BaseModel):
    id: UUID
    institution_id: int
    course_id: int
    academic_year: str
    required_count: int
    total_existing: int
    effective_existing: int
    suggested_vacancy: int
    confirmed_vacancy: Optional[int] = None
    status: str
    ai_suggestion_notes: Optional[str] = None
    anomaly_count: int
    unacknowledged_high_count: int
    anomalies: List[AnomalyResponse] = []
    
    # Dynamic/Fetched fields for frontend UI
    approved_seats: Optional[int] = None
    actual_admitted: Optional[int] = None
    ai_analysis: Optional[dict] = None
    previous_vacancy: int = 0
    ratio: int = 20
    
    model_config = ConfigDict(from_attributes=True)


class VacancyConfirmRequest(BaseModel):
    confirmed_vacancy: int


class AnomalyAcknowledgeRequest(BaseModel):
    remarks: str
