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

def check_individual_faculty(
    faculty: ExistingFaculty, 
    course_name: str, 
    norm_info: dict = None
) -> List[AnomalyResult]:
    """Check anomalies for a single faculty member."""
    anomalies = []
    
    # 1. Deputation Check
    if faculty.employment_type == "DEPUTED_IN":
        anomalies.append(AnomalyResult(
            anomaly_type="MISSING_DEPUTATION_ORDER",
            severity="MEDIUM",
            description=f"Faculty {faculty.full_name} is marked DEPUTED_IN. Verify deputation order.",
            faculty_id=str(faculty.id)
        ))

    # 2. Course Specialization Match
    branch_keywords = set(course_name.lower().split())
    if faculty.specialization:
        spec_keywords = set(faculty.specialization.lower().split())
        if not (branch_keywords & spec_keywords): # No intersection
            anomalies.append(AnomalyResult(
                anomaly_type="QUALIFICATION_MISMATCH",
                severity="MEDIUM",
                description=f"Faculty {faculty.full_name} specialization ({faculty.specialization}) may not match course {course_name}.",
                faculty_id=str(faculty.id)
            ))

    # 3. Norm-based Checks
    if norm_info:
        min_qual = norm_info.get("min_qualification", "").lower()
        max_age = norm_info.get("max_age", 38)

        # Qualification Check
        if min_qual and faculty.qualification:
            import re
            fac_qual_clean = re.sub(r'[^a-z0-9]', '', faculty.qualification.lower())
            min_qual_clean = re.sub(r'[^a-z0-9]', '', min_qual.lower())
            
            print(f"DEBUG: fac_qual_clean='{fac_qual_clean}', min_qual_clean='{min_qual_clean}'")
            print(f"DEBUG: fac in min: {fac_qual_clean in min_qual_clean}, min in fac: {min_qual_clean in fac_qual_clean}")
            
            if fac_qual_clean not in min_qual_clean and min_qual_clean not in fac_qual_clean:
                print("DEBUG: Entered anomaly block!")
                found = False
                if hasattr(faculty, "qualifications_list") and faculty.qualifications_list:
                    for q in faculty.qualifications_list:
                        if not q.degree: continue
                        q_deg_clean = re.sub(r'[^a-z0-9]', '', q.degree.lower())
                        if q_deg_clean in min_qual_clean or min_qual_clean in q_deg_clean:
                            found = True
                            break
                
                if not found:
                    anomalies.append(AnomalyResult(
                        anomaly_type="UNDER_QUALIFIED",
                        severity="HIGH",
                        description=f"Faculty {faculty.full_name} qualification ({faculty.qualification}) does not meet norm ({min_qual}).",
                        faculty_id=str(faculty.id)
                    ))

        # Age Check
        if faculty.date_of_birth:
            age = calculate_age(faculty.date_of_birth)
            if age > max_age:
                anomalies.append(AnomalyResult(
                    anomaly_type="OVER_AGE",
                    severity="HIGH",
                    description=f"Faculty {faculty.full_name} age ({age}) exceeds maximum norm ({max_age}).",
                    faculty_id=str(faculty.id)
                ))

    return anomalies

def run_vacancy_anomaly_check(
    faculty_list: List[ExistingFaculty], 
    assessment: VacancyAssessment, 
    course_name: str, 
    norm_info: dict = None,
    previous_year_confirmed: int = None
) -> List[AnomalyResult]:
    """Bulk check for an entire assessment context."""
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

    # 3. Previous Year Consistency
    if previous_year_confirmed is not None and assessment.suggested_vacancy == previous_year_confirmed:
        anomalies.append(AnomalyResult(
            anomaly_type="UNCHANGED_VACANCY",
            severity="LOW",
            description="Vacancy count unchanged from previous academic year."
        ))

    # 4. Individual Faculty Checks
    for faculty in faculty_list:
        anomalies.extend(check_individual_faculty(faculty, course_name, norm_info))

    return anomalies
