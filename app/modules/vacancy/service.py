import math
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_
from sqlalchemy.orm import selectinload

from app.models.existing_faculty import ExistingFaculty
from app.models.faculty_qualification import FacultyQualification
from app.models.vacancy_assessment import VacancyAssessment
from app.models.vacancy_anomaly import VacancyAnomaly
from app.models.faculty_req import FacultyRequirement
from app.models.institution import Course
from app.models.audit import AuditLog
from app.modules.vacancy.schemas import FacultyCreateRequest, FacultyUpdateRequest, VacancyConfirmRequest
from app.modules.vacancy.anomaly_engine import run_vacancy_anomaly_check

class VacancyService:
    @staticmethod
    async def log_audit(db: AsyncSession, entity_name: str, entity_id: str, action: str, user_id: int, old_val: dict = None, new_val: dict = None):
        audit = AuditLog(
            entity_name=entity_name, 
            entity_id=str(entity_id), # Ensure string conversion for UUIDs
            action=action, 
            user_id=user_id, 
            old_value=old_val, 
            new_value=new_val
        )
        db.add(audit)

    @staticmethod
    def calculate_is_effective(status: str) -> bool:
        return status not in ["DEPUTED_OUT", "RETIRED"]

    async def add_faculty(self, db: AsyncSession, user_id: int, req: FacultyCreateRequest):
        # 1. Reject future date_of_joining
        if req.date_of_joining > date.today():
            raise HTTPException(status_code=400, detail="Date of joining cannot be in the future")

        # 2. Duplicate employee_id check
        stmt = select(ExistingFaculty).filter(
            ExistingFaculty.institution_id == req.institution_id,
            ExistingFaculty.employee_id == req.employee_id,
            ExistingFaculty.academic_year == req.academic_year
        )
        result = await db.execute(stmt)
        if result.scalars().first():
            raise HTTPException(status_code=400, detail="Employee ID already exists for this institution and year")

        # 3. Create Faculty
        is_effective = self.calculate_is_effective(req.status)
        faculty = ExistingFaculty(
            institution_id=req.institution_id,
            course_id=req.course_id,
            employee_id=req.employee_id,
            full_name=req.full_name,
            designation=req.designation,
            employment_type=req.employment_type,
            qualification=req.qualification,
            specialization=req.specialization,
            date_of_joining=req.date_of_joining,
            date_of_birth=req.date_of_birth,
            status=req.status,
            is_effective=is_effective,
            academic_year=req.academic_year,
            entered_by=user_id
        )
        db.add(faculty)
        await db.flush()

        # 4. Add Qualifications
        for q in req.qualifications:
            qual = FacultyQualification(
                faculty_id=faculty.id,
                degree=q.degree,
                specialization=q.specialization,
                university=q.university,
                year_of_passing=q.year_of_passing,
                is_highest=q.is_highest
            )
            db.add(qual)

        # 5. Reset related assessments to DRAFT
        await self.reset_assessment_to_draft(db, req.institution_id, req.course_id, req.academic_year)
        
        await self.log_audit(db, "ExistingFaculty", str(faculty.id), "CREATE", user_id, new_val=req.model_dump(mode="json"))
        await db.commit()
        await db.refresh(faculty)
        return faculty

    async def update_faculty(self, db: AsyncSession, user_id: int, faculty_id: UUID, req: FacultyUpdateRequest):
        stmt = select(ExistingFaculty).filter(ExistingFaculty.id == faculty_id).options(selectinload(ExistingFaculty.qualifications_list))
        result = await db.execute(stmt)
        faculty = result.scalars().first()
        if not faculty:
            raise HTTPException(status_code=404, detail="Faculty not found")

        old_data = {
            "status": faculty.status,
            "full_name": faculty.full_name,
            # ... add more as needed for audit
        }

        update_data = req.model_dump(exclude_unset=True)
        if "status" in update_data:
            faculty.is_effective = self.calculate_is_effective(update_data["status"])
            await self.reset_assessment_to_draft(db, faculty.institution_id, faculty.course_id, faculty.academic_year)

        for key, value in update_data.items():
            if key not in ["qualifications"]:
                setattr(faculty, key, value)

        await self.log_audit(db, "ExistingFaculty", str(faculty.id), "UPDATE", user_id, old_val=old_data, new_val=update_data)
        await db.commit()
        await db.refresh(faculty)
        return faculty

    async def soft_delete_faculty(self, db: AsyncSession, user_id: int, faculty_id: UUID, reason: str):
        stmt = select(ExistingFaculty).filter(ExistingFaculty.id == faculty_id)
        result = await db.execute(stmt)
        faculty = result.scalars().first()
        if not faculty:
            raise HTTPException(status_code=404, detail="Faculty not found")

        faculty.status = "DELETED" # Or just is_active = False if we had that column. User said "soft delete only"
        faculty.is_effective = False
        
        await self.reset_assessment_to_draft(db, faculty.institution_id, faculty.course_id, faculty.academic_year)
        await self.log_audit(db, "ExistingFaculty", str(faculty.id), "DELETE", user_id, old_val={"status": "ACTIVE"}, new_val={"status": "DELETED", "reason": reason})
        await db.commit()

    async def get_faculty_list(self, db: AsyncSession, institution_id: int, course_id: int, academic_year: str, skip: int = 0, limit: Optional[int] = None):
        base_filter = and_(
            ExistingFaculty.institution_id == institution_id,
            ExistingFaculty.course_id == course_id,
            ExistingFaculty.academic_year == academic_year
        )

        total_stmt = select(func.count()).select_from(ExistingFaculty).where(base_filter)
        total_res = await db.execute(total_stmt)
        total = total_res.scalar_one()

        effective_stmt = select(func.count()).select_from(ExistingFaculty).where(base_filter, ExistingFaculty.is_effective == True)
        effective_res = await db.execute(effective_stmt)
        effective = effective_res.scalar_one()

        non_effective = total - effective

        stmt = select(ExistingFaculty).filter(base_filter).options(selectinload(ExistingFaculty.qualifications_list))
        if limit is not None:
            stmt = stmt.offset(skip).limit(limit)
            
        result = await db.execute(stmt)
        items = result.scalars().all()
        
        return items, total, effective, non_effective

    async def suggest_vacancy(self, db: AsyncSession, user_id: int, institution_id: int, course_id: int, academic_year: str):
        # 1. Gate: Check Step 1 Approval
        # Intake is identified by Course + year.
        from app.models.intake import IntakeDefinition
        intake_stmt = select(IntakeDefinition).filter(
            IntakeDefinition.course_id == course_id,
            IntakeDefinition.academic_year == academic_year
        )
        intake_res = await db.execute(intake_stmt)
        intake = intake_res.scalars().first()
        if not intake:
            raise HTTPException(status_code=400, detail="Step 1 Intake not defined for this Course and year")

        req_stmt = select(FacultyRequirement).filter(FacultyRequirement.intake_id == intake.id)
        req_res = await db.execute(req_stmt)
        requirement = req_res.scalars().first()
        if not requirement:
            raise HTTPException(status_code=400, detail="Faculty Requirement not generated yet (Step 1)")

        # In a real DTE system, we'd check a status column on requirement. 
        # For now, if it exists, we proceed.

        # 1b. Resolve Norm for anomaly checks
        from app.modules.requirements.norm_service import resolve_norm as svc_resolve_norm
        from app.modules.requirements.norms_service import derive_course_category
        from app.modules.requirements.norm_constants import CourseCategory

        course_stmt = select(Course).filter(Course.id == course_id)
        course_obj = (await db.execute(course_stmt)).scalars().first()
        
        course_cat = None
        if course_obj:
            legacy_cat = derive_course_category(course_obj.name, course_obj.level)
            _legacy_map = {
                "Engineering Diploma": CourseCategory.ENGINEERING_DIPLOMA,
                "Engineering Degree": CourseCategory.ENGINEERING_DEGREE,

                "HMCT": CourseCategory.HMCT,
                "Applied Sciences": CourseCategory.APPLIED_SCIENCES,
            }
            course_cat = _legacy_map.get(legacy_cat)

        norm = await svc_resolve_norm(institution_id, academic_year, course_cat, db)
        norm_info = {
            "min_qualification": norm.min_qualification,
            "grade_requirement": norm.grade_requirement,
            "max_age": norm.max_age,
            "workload_hours_per_week": norm.workload_hours_per_week,
            "faculty_student_ratio": norm.faculty_student_ratio
        }

        # 2. Run Anomaly Checks (Qualification & Age Validation)
        from app.modules.vacancy.anomaly_engine import run_vacancy_anomaly_check
        
        faculty_items, total, effective, _ = await self.get_faculty_list(db, institution_id, course_id, academic_year)
        
        # Clear existing anomalies for this context (re-run)
        # (This is handled by run_vacancy_anomaly_check if we pass assessment later)
        
        # Calculate Qualified Effective Faculty
        # An existing faculty only reduces vacancy if they are NOT under-qualified and NOT over-age
        qualified_effective = 0
        for f in faculty_items:
            # We treat only effective faculty for vacancy reduction
            if f.employment_type in ["PERMANENT", "CONTRACT", "PROBATION"]:
                # Check for high-severity anomalies that disqualify them for vacancy reduction
                anoms = run_vacancy_anomaly_check(f, norm_info, course_obj.name if course_obj else "Unknown")
                is_qualified = not any(a["type"] in ["UNDER_QUALIFIED", "OVER_AGE"] for a in anoms)
                if is_qualified:
                    qualified_effective += 1

        # 3. Compute counts based on Qualified Effective Faculty
        suggested = requirement.computed_required_count - qualified_effective
        notes = f"AI Suggested based on {requirement.computed_required_count} required and {qualified_effective} qualified faculty."
        
        if qualified_effective < effective:
            diff = effective - qualified_effective
            notes += f" Note: {diff} existing faculty members were flagged as under-qualified or over-age and excluded from calculation."

        if suggested < 0:
            suggested = 0
            notes = "SURPLUS: Existing qualified faculty exceeds required count."

        # 4. Upsert VacancyAssessment
        assess_stmt = select(VacancyAssessment).filter(
            VacancyAssessment.institution_id == institution_id,
            VacancyAssessment.course_id == course_id,
            VacancyAssessment.academic_year == academic_year
        )
        assess_res = await db.execute(assess_stmt)
        assessment = assess_res.scalars().first()

        if not assessment:
            assessment = VacancyAssessment(
                institution_id=institution_id,
                course_id=course_id,
                academic_year=academic_year,
                requirement_id=requirement.id,
                required_count=requirement.computed_required_count,
                total_existing=total,
                effective_existing=effective,
                suggested_vacancy=suggested
            )
            db.add(assessment)
            await db.flush()
        
        # 5. Persist the updated state and Run Anomalies to DB
        from app.models.vacancy_assessment import Anomaly
        from app.modules.vacancy.anomaly_engine import run_vacancy_anomaly_check
        
        # Clear old anomalies
        from sqlalchemy import delete
        await db.execute(delete(Anomaly).filter(Anomaly.assessment_id == assessment.id))

        for f in faculty_items:
            anoms = run_vacancy_anomaly_check(f, norm_info, course_obj.name if course_obj else "Unknown")
            for a_data in anoms:
                new_a = Anomaly(
                    assessment_id=assessment.id,
                    faculty_id=f.id,
                    type=a_data["type"],
                    severity=a_data["severity"],
                    message=a_data["message"]
                )
                db.add(new_a)

        if assessment.status != "CONFIRMED":
            assessment.required_count = requirement.computed_required_count
            assessment.total_existing = total
            assessment.effective_existing = effective
            assessment.suggested_vacancy = suggested
            assessment.ai_suggestion_notes = notes
            assessment.status = "AI_SUGGESTED"
        else:
            # If confirmed, only update the computed values but keep status
            assessment.required_count = requirement.computed_required_count
            assessment.total_existing = total
            assessment.effective_existing = effective

        # 4. Anomaly Engine
        course_stmt = select(Course).filter(Course.id == course_id)
        course_res = await db.execute(course_stmt)
        Course = course_res.scalars().first()
        
        # Query previous year confirmed
        prev_year = str(int(academic_year.split('-')[0]) - 1) + "-" + str(int(academic_year.split('-')[1]) - 1)
        prev_stmt = select(VacancyAssessment).filter(
            VacancyAssessment.institution_id == institution_id,
            VacancyAssessment.course_id == course_id,
            VacancyAssessment.academic_year == prev_year
        )
        prev_res = await db.execute(prev_stmt)
        prev_assessment = prev_res.scalars().first()
        prev_confirmed = prev_assessment.confirmed_vacancy if prev_assessment else None

        anomalies_data = run_vacancy_anomaly_check(
            faculty_items, assessment, course_obj.name if course_obj else "Unknown", norm_info, prev_confirmed
        )

        # 4b. Refine suggested_vacancy if critical anomalies found (e.g. Under-qualified shouldn't count)
        qualified_effective = effective
        for a in anomalies_data:
            if a.severity == "HIGH" and a.anomaly_type in ["UNDER_QUALIFIED", "OVER_AGE"]:
                # If a faculty is effective but not qualified, they don't fill the requirement
                qualified_effective -= 1
        
        # Recalculate suggested based on QUALIFIED faculty
        new_suggested = requirement.computed_required_count - qualified_effective
        if new_suggested < 0: new_suggested = 0
        
        if assessment.status != "CONFIRMED":
            assessment.suggested_vacancy = new_suggested
            if qualified_effective < effective:
                assessment.ai_suggestion_notes = f"Adjusted: {effective - qualified_effective} existing faculty are under-qualified/over-age."
        
        # 5. Clear old anomalies
        await db.execute(delete(VacancyAnomaly).filter(VacancyAnomaly.assessment_id == assessment.id))
        
        for a in anomalies_data:
            db.add(VacancyAnomaly(
                assessment_id=assessment.id,
                anomaly_type=a.anomaly_type,
                severity=a.severity,
                description=a.description,
                faculty_id=UUID(a.faculty_id) if a.faculty_id else None
            ))

        await self.log_audit(db, "VacancyAssessment", str(assessment.id), "SUGGEST", user_id, new_val={"suggested": suggested})
        await db.commit()
        
        # Re-fetch with anomalies loaded
        final_stmt = select(VacancyAssessment).filter(VacancyAssessment.id == assessment.id).options(selectinload(VacancyAssessment.anomalies))
        final_res = await db.execute(final_stmt)
        return final_res.scalars().first()

    async def confirm_vacancy(self, db: AsyncSession, user_id: int, institution_id: int, course_id: int, academic_year: str, req: VacancyConfirmRequest):
        stmt = select(VacancyAssessment).filter(
            VacancyAssessment.institution_id == institution_id,
            VacancyAssessment.course_id == course_id,
            VacancyAssessment.academic_year == academic_year
        ).options(selectinload(VacancyAssessment.anomalies))
        result = await db.execute(stmt)
        assessment = result.scalars().first()
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        # 1. Block if already CONFIRMED
        if assessment.status == "CONFIRMED":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Assessment is already confirmed and cannot be edited")

        # 2. Gate: All HIGH severity anomalies must be acknowledged
        unacknowledged_high = [a for a in assessment.anomalies if a.severity == "HIGH" and not a.is_acknowledged]
        if unacknowledged_high:
            raise HTTPException(status_code=400, detail="All HIGH severity anomalies must be acknowledged before confirmation")

        # 3. Logic for LOW severity audit flag
        if abs(req.confirmed_vacancy - assessment.suggested_vacancy) > 2:
            await self.log_audit(db, "VacancyAssessment", str(assessment.id), "SIGNIFICANT_DEVIATION", user_id, 
                               new_val={"suggested": assessment.suggested_vacancy, "confirmed": req.confirmed_vacancy})

        assessment.confirmed_vacancy = req.confirmed_vacancy
        assessment.status = "CONFIRMED"
        assessment.confirmed_by = user_id
        assessment.confirmed_at = datetime.now()

        await self.log_audit(db, "VacancyAssessment", str(assessment.id), "CONFIRM", user_id, new_val={"confirmed": req.confirmed_vacancy})
        await db.commit()
        
        # Re-fetch with anomalies loaded
        final_stmt = select(VacancyAssessment).filter(VacancyAssessment.id == assessment.id).options(selectinload(VacancyAssessment.anomalies))
        final_res = await db.execute(final_stmt)
        return final_res.scalars().first()

    async def acknowledge_anomaly(self, db: AsyncSession, user_id: int, anomaly_id: UUID, remarks: str):
        stmt = select(VacancyAnomaly).filter(VacancyAnomaly.id == anomaly_id)
        result = await db.execute(stmt)
        anomaly = result.scalars().first()
        if not anomaly:
            raise HTTPException(status_code=404, detail="Anomaly not found")

        anomaly.is_acknowledged = True
        anomaly.acknowledged_by = user_id
        anomaly.acknowledged_at = datetime.now()
        anomaly.description += f" [REMARKS: {remarks}]"

        await self.log_audit(db, "VacancyAnomaly", str(anomaly.id), "ACKNOWLEDGE", user_id, new_val={"remarks": remarks})
        await db.commit()
        return anomaly

    async def reset_assessment_to_draft(self, db: AsyncSession, institution_id: int, course_id: int, academic_year: str):
        stmt = update(VacancyAssessment).filter(
            VacancyAssessment.institution_id == institution_id,
            VacancyAssessment.course_id == course_id,
            VacancyAssessment.academic_year == academic_year
        ).values(status="DRAFT")
        await db.execute(stmt)
