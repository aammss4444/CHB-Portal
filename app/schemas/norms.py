from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.requirements.norm_constants import CourseCategory, DTE_COURSE_NORM_DEFAULTS, NormType

# ---------------------------------------------------------------------------
# Legacy constants — kept for backward compatibility with existing imports
# ---------------------------------------------------------------------------
NORM_TYPES = ["COURSE_WISE", "GENERAL"]
COURSE_CATEGORIES = [
    "Engineering Diploma",
    "Engineering Degree",

    "HMCT",
    "Applied Sciences",
]
COURSE_WISE_DTE_DEFAULTS = {
    "Engineering Diploma": {"qualification": "B.E/B.Tech", "grade": "First Class"},
    "Engineering Degree": {"qualification": "M.E/M.Tech", "grade": "First Class"},

    "HMCT": {"qualification": "Bachelor in Hotel Management", "grade": "First Class"},
    "Applied Sciences": {"qualification": "M.Sc (Physics/Chemistry/Maths)", "grade": "First Class"},
}


# ---------------------------------------------------------------------------
# NormCreate — extended with NormType enum + model_validator
# ---------------------------------------------------------------------------
class NormCreate(BaseModel):
    academic_year: Optional[str] = Field(None, description="e.g., 2026-27")
    norm_type: NormType
    institution_id: Optional[int] = None
    course_id: Optional[int] = None
    course_category: Optional[CourseCategory] = None

    min_qualification: str
    grade_requirement: str
    faculty_student_ratio: float
    max_age: int = 38
    workload_hours_per_week: int = 18


    @model_validator(mode="after")
    def validate_course_category(self) -> "NormCreate":
        if self.norm_type == NormType.COURSE_WISE and not self.course_id:
            raise ValueError("course_id is required when norm_type is COURSE_WISE")
        if self.norm_type == NormType.GENERAL and self.course_id is not None:
            raise ValueError("course_id must be null when norm_type is GENERAL")
        return self


class NormUpdate(BaseModel):
    academic_year: Optional[str] = None
    norm_type: Optional[Literal["COURSE_WISE", "GENERAL"]] = None
    institution_id: Optional[int] = None
    course_id: Optional[int] = None
    course_category: Optional[str] = None
    min_qualification: Optional[str] = None
    grade_requirement: Optional[str] = None
    faculty_student_ratio: Optional[float] = None
    max_age: Optional[int] = None
    workload_hours_per_week: Optional[int] = None



# ---------------------------------------------------------------------------
# NormResponse — institution-scoped, uses NormType enum
# ---------------------------------------------------------------------------
class NormResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    institution_id: Optional[int] = None
    course_id: Optional[int] = None
    academic_year: Optional[str] = None
    norm_type: Optional[NormType] = None
    course_category: Optional[CourseCategory] = None
    min_qualification: Optional[str] = None
    grade_requirement: Optional[str] = None
    faculty_student_ratio: float
    max_age: Optional[int] = None
    workload_hours_per_week: Optional[int] = None
    pass


# ---------------------------------------------------------------------------
# DTE seed request / response
# ---------------------------------------------------------------------------
class SeedDTEDefaultsRequest(BaseModel):
    institution_id: int
    academic_year: str
    faculty_student_ratio: int = Field(..., description="Applied to all 5 seeded categories")


class SeedDTEDefaultsResponse(BaseModel):
    seeded: int
    skipped: int
    detail: List[str] = Field(..., description="One line per category: 'seeded' or 'skipped'")


# ---------------------------------------------------------------------------
# NormUsedResponse — embedded in requirement generation response
# ---------------------------------------------------------------------------
class NormUsedResponse(BaseModel):
    type: NormType
    course_id: Optional[int] = None
    course_category: Optional[CourseCategory] = None
    min_qualification: str
    grade_requirement: str
    faculty_student_ratio: float
