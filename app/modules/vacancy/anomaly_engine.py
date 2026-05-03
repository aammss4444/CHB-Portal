from typing import List, Optional
from datetime import date
from dataclasses import dataclass
from app.models.existing_faculty import ExistingFaculty
from app.models.vacancy_assessment import VacancyAssessment

@dataclass
class AnomalyResult:
    anomaly_type: str
    severity: str
    description: str
    faculty_id: str = None

def calculate_age(dob: date) -> int:
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

def run_vacancy_anomaly_check(
    faculty_list: List[ExistingFaculty], 
    assessment: VacancyAssessment, 
    course_name: str, 
    norm_info: dict = None,
    previous_year_confirmed: int = None
) -> List[AnomalyResult]:
    anomalies = []

    # 1. suggested_vacancy > 50% of required_count
    if assessment.required_count > 0:
        ratio = (assessment.suggested_vacancy / assessment.required_count) * 100
        if ratio > 50:
            anomalies.append(AnomalyResult(
                anomaly_type="HIGH_VACANCY_RATIO",
                severity="HIGH",
                description=f"Vacancy count is {ratio:.1f}% of required. Verify all faculty data is entered."
            ))

    # 2. effective_existing == 0
    if assessment.effective_existing == 0:
        anomalies.append(AnomalyResult(
            anomaly_type="NO_FACULTY_ENTERED",
            severity="HIGH",
            description="No effective faculty found for this course and year."
        ))

    # 3. Employment Type & Deputation
    for faculty in faculty_list:
        if faculty.employment_type == "DEPUTED_IN":
            anomalies.append(AnomalyResult(
                anomaly_type="MISSING_DEPUTATION_ORDER",
                severity="MEDIUM",
                description=f"Faculty {faculty.full_name} is marked DEPUTED_IN. Verify deputation order.",
                faculty_id=str(faculty.id)
            ))

    # 4. Previous Year Consistency
    if previous_year_confirmed is not None and assessment.suggested_vacancy == previous_year_confirmed:
        anomalies.append(AnomalyResult(
            anomaly_type="UNCHANGED_VACANCY",
            severity="LOW",
            description="Vacancy count unchanged from previous academic year."
        ))

    # 5. Course Specialization Match
    branch_keywords = set(course_name.lower().split())
    for faculty in faculty_list:
        if faculty.specialization:
            spec_keywords = set(faculty.specialization.lower().split())
            if not (branch_keywords & spec_keywords): # No intersection
                anomalies.append(AnomalyResult(
                    anomaly_type="QUALIFICATION_MISMATCH",
                    severity="MEDIUM",
                    description=f"Faculty {faculty.full_name} specialization ({faculty.specialization}) may not match course {course_name}.",
                    faculty_id=str(faculty.id)
                ))

    # --- NEW: Norm-based Anomalies ---
    if norm_info:
        min_qual = norm_info.get("min_qualification", "").lower()
        grade_req = norm_info.get("grade_requirement", "").lower()
        max_age = norm_info.get("max_age", 38)
        norm_workload = norm_info.get("workload_hours_per_week", 18)

        for faculty in faculty_list:
            # 6. Qualification Check (Simple contains)
            if min_qual and faculty.qualification:
                if min_qual not in faculty.qualification.lower():
                    # Check in qualifications_list if available
                    found = False
                    if hasattr(faculty, "qualifications_list"):
                        for q in faculty.qualifications_list:
                            if min_qual in q.degree.lower():
                                found = True
                                break
                    
                    if not found:
                        anomalies.append(AnomalyResult(
                            anomaly_type="UNDER_QUALIFIED",
                            severity="HIGH",
                            description=f"Faculty {faculty.full_name} qualification ({faculty.qualification}) does not meet norm ({min_qual}).",
                            faculty_id=str(faculty.id)
                        ))

            # 7. Age Check
            if faculty.date_of_birth:
                age = calculate_age(faculty.date_of_birth)
                if age > max_age:
                    anomalies.append(AnomalyResult(
                        anomaly_type="OVER_AGE",
                        severity="HIGH",
                        description=f"Faculty {faculty.full_name} age ({age}) exceeds maximum norm ({max_age}).",
                        faculty_id=str(faculty.id)
                    ))

            # 8. Grade Requirement (informational anomaly)
            # Since we don't store grades for existing faculty yet, we flag it as a reminder
            if grade_req and "first class" in grade_req:
                # This would ideally check the faculty's grade if we had it.
                pass

    return anomalies
