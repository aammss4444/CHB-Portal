from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime
from app.schemas.requirement_ai import AIResponse
from app.modules.requirements.norm_constants import CourseCategory


# --- Norms (kept here for backward compat; canonical source is app/schemas/norms.py) ---
class NormCreate(BaseModel):
    academic_year: Optional[str] = Field(None, description="e.g., 2026-27")
    norm_type: str = Field(..., description="COURSE_WISE or GENERAL")
    course_category: Optional[str] = None
    faculty_student_ratio: float = Field(..., description="e.g., 20.0 for 1:20")
    min_qualification: Optional[str] = None
    grade_requirement: Optional[str] = None
    max_age: int = 38
    workload_hours_per_week: int = 18



class NormResponse(NormCreate):
    id: int

    class Config:
        from_attributes = True


class NormUpdate(BaseModel):
    academic_year: Optional[str] = None
    norm_type: Optional[str] = None
    course_category: Optional[str] = None
    faculty_student_ratio: Optional[float] = None
    min_qualification: Optional[str] = None
    grade_requirement: Optional[str] = None
    max_age: Optional[int] = None
    workload_hours_per_week: Optional[int] = None



# --- Institutions & Courses ---
class CourseCreate(BaseModel):
    name: str = Field(..., description="e.g., Computer Engineering")
    level: str = Field(..., description="Diploma, Degree, D.Pharm, etc.")


class InstitutionCreate(BaseModel):
    name: str = Field(..., description="e.g., Govt College Pune")
    code: str = Field(..., description="Unique DTE code")
    district: str
    type: str
    courses: List[CourseCreate] = []


class CourseResponse(CourseCreate):
    id: int
    institution_id: int

    class Config:
        from_attributes = True


class InstitutionResponse(BaseModel):
    id: int
    name: str
    code: str
    district: str
    type: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    courses: List[CourseResponse] = []

    class Config:
        from_attributes = True


class CourseUpdate(BaseModel):
    name: Optional[str] = None
    level: Optional[str] = None


class InstitutionUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    district: Optional[str] = None
    type: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


# --- Intake & Requirements ---
class IntakeCreate(BaseModel):
    institution_id: int
    course_id: int = Field(..., description="ID of the course")
    academic_year: str = Field(..., description="e.g., 2026-2027")
    approved_seats: int
    actual_admitted: int


class IntakeUpdate(BaseModel):
    approved_seats: Optional[int] = None
    actual_admitted: Optional[int] = None


class IntakeResponse(BaseModel):
    id: int
    institution_id: int
    course_id: int
    course_name: str
    academic_year: str
    approved_seats: int
    actual_admitted: int

    class Config:
        from_attributes = True


# --- Unified Course Setup (Intake + Norm) ---
class CourseSetupRequest(BaseModel):
    """Single API payload to define both intake and norm for a specific course."""
    institution_id: int = Field(..., description="ID of the institution")
    course_name: str = Field(..., description="Exact course name, e.g., Computer Engineering")
    academic_year: str = Field(..., description="e.g., 2026-2027")

    # Intake fields
    approved_seats: int = Field(..., ge=1, description="AICTE/DTE approved intake capacity")
    actual_admitted: int = Field(..., ge=0, description="Actual students admitted this year")

    # Norm fields
    faculty_student_ratio: float = Field(..., gt=0, description="e.g., 20.0 means 1:20")
    min_qualification: str = Field(..., description="e.g., B.E./B.Tech in relevant course")
    grade_requirement: str = Field(..., description="e.g., First Class")
    norm_type: str = Field(default="COURSE_WISE", description="COURSE_WISE or GENERAL")
    course_category: Optional[str] = Field(None, description="DTE course category, auto-derived if omitted")
    max_age: int = Field(default=38, description="Maximum age limit for faculty")
    workload_hours_per_week: int = Field(default=18, description="Weekly workload hours")


class CourseSetupIntakeDetail(BaseModel):
    id: int
    course_id: int
    course_name: str
    academic_year: str
    approved_seats: int
    actual_admitted: int

    class Config:
        from_attributes = True


class CourseSetupNormDetail(BaseModel):
    id: int
    institution_id: int
    course_id: int
    norm_type: str
    course_category: Optional[str] = None
    faculty_student_ratio: float
    min_qualification: str
    grade_requirement: str
    max_age: int
    workload_hours_per_week: int

    class Config:
        from_attributes = True


class CourseSetupResponse(BaseModel):
    status: str = "success"
    institution_id: int
    course_name: str
    academic_year: str
    intake: CourseSetupIntakeDetail
    norm: CourseSetupNormDetail


class GenerateRequirementRequest(BaseModel):
    institution_id: int
    academic_year: str
    course_id: Optional[int] = None
    course_category: Optional[str] = None


class AnomalyResponse(BaseModel):
    id: int
    severity: str
    description: str
    is_acknowledged: bool

    class Config:
        from_attributes = True


class RequirementResponse(BaseModel):
    id: int
    intake_id: int
    computed_required_count: int
    formula_breakdown: Any  # JSONB
    created_at: datetime
    anomalies: List[AnomalyResponse] = []
    required_faculty: Optional[int] = None
    norm_used: Optional[Any] = None

    class Config:
        from_attributes = True



class AIQueryRequest(BaseModel):
    query: str = Field(..., description="The free-text question for the AI")
    institution_id: Optional[int] = None
    context: Optional[Dict[str, Any]] = None

class AIQueryResponse(BaseModel):
    answer: str
    data: Optional[Dict[str, Any]] = None
    confidence_score: float = 1.0
