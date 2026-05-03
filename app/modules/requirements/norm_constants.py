"""
DTE Norm constants for CHB Portal — Step 1 Faculty Requirement Generation.

NormType and CourseCategory are Python-level enums; norm_type is stored as
VARCHAR in the database to avoid PostgreSQL enum migration complexity.
"""

from enum import Enum


class NormType(str, Enum):
    COURSE_WISE = "COURSE_WISE"
    GENERAL = "GENERAL"


class CourseCategory(str, Enum):
    ENGINEERING_DIPLOMA = "Engineering & Technology (Diploma)"

    ENGINEERING_DEGREE = "Engineering (Degree - B.E./B.Tech)"
    HMCT = "HMCT (Hotel Management)"
    APPLIED_SCIENCES = "Non-Engineering (Applied Sciences)"


# Source: DTE norms document — Visiting Lecturer / CHB roles
# DO NOT change these values without updating the DTE reference document
DTE_COURSE_NORM_DEFAULTS: dict = {
    CourseCategory.ENGINEERING_DIPLOMA: {
        "min_qualification": "B.E./B.Tech in relevant course",
        "grade_requirement": "First Class",
    },

    CourseCategory.ENGINEERING_DEGREE: {
        "min_qualification": "M.E./M.Tech in relevant course",
        "grade_requirement": "First Class at Bachelor's or Master's level",
    },
    CourseCategory.HMCT: {
        "min_qualification": "Bachelor's degree in Hotel Management",
        "grade_requirement": "First Class",
    },
    CourseCategory.APPLIED_SCIENCES: {
        "min_qualification": "Master's degree in Physics, Chemistry or Maths",
        "grade_requirement": "First Class",
    },
}
