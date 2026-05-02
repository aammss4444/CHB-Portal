from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.vacancy.service import VacancyService
from app.modules.vacancy.schemas import (
    FacultyCreateRequest, FacultyUpdateRequest, FacultyListResponse,
    VacancySuggestRequest, VacancyAssessmentResponse, VacancyConfirmRequest,
    AnomalyAcknowledgeRequest
)
from app.models.user import User
from app.modules.vacancy.ai_engine import VacancyAIEngine
from app.modules.vacancy.ai_service import VacancyAIService

class VacancyController:
    def __init__(self):
        self.service = VacancyService()
        self.ai_engine = VacancyAIEngine()
        self.ai_service = VacancyAIService(self.ai_engine)

    async def add_faculty(self, db: AsyncSession, current_user: User, req: FacultyCreateRequest):
        faculty = await self.service.add_faculty(db, current_user.id, req)
        return {"status": "success", "data": faculty}

    async def update_faculty(self, db: AsyncSession, current_user: User, faculty_id: UUID, req: FacultyUpdateRequest):
        faculty = await self.service.update_faculty(db, current_user.id, faculty_id, req)
        return {"status": "success", "data": faculty}

    async def get_faculty_list(self, db: AsyncSession, current_user: User, institution_id: int, course_id: int, academic_year: str, skip: int = 0, limit: int = 100):
        items, total, effective, non_effective = await self.service.get_faculty_list(db, institution_id, course_id, academic_year, skip, limit)
        import math
        return {
            "status": "success",
            "data": items,
            "total": total,
            "page": (skip // limit) + 1 if limit > 0 else 1,
            "limit": limit,
            "total_pages": math.ceil(total / limit) if limit > 0 else 0,
            "meta": {
                "effective_count": effective,
                "non_effective_count": non_effective
            }
        }

    async def delete_faculty(self, db: AsyncSession, current_user: User, faculty_id: UUID, reason: str = "No reason provided"):
        await self.service.soft_delete_faculty(db, current_user.id, faculty_id, reason)
        return {"status": "success", "message": "Faculty deleted successfully"}

    async def suggest_vacancy(self, db: AsyncSession, current_user: User, req: VacancySuggestRequest):
        # 1. Deterministic Logic (Rule-based calculation)
        assessment = await self.service.suggest_vacancy(db, current_user.id, req.institution_id, req.course_id, req.academic_year)
        
        # 2. Fetch Data for AI (Intake, Norms, Institution)
        from sqlalchemy import select
        from app.models.institution import Institution, Course
        from app.models.intake import IntakeDefinition
        from app.models.norm import Norm
        
        # Institution Info
        inst_stmt = select(Institution).filter(Institution.id == req.institution_id)
        inst_obj = (await db.execute(inst_stmt)).scalars().first()
        
        # Course Info
        course_stmt = select(Course).filter(Course.id == req.course_id)
        course_obj = (await db.execute(course_stmt)).scalars().first()
        
        # Intake Definition
        intake_stmt = select(IntakeDefinition).filter(
            IntakeDefinition.course_id == req.course_id,
            IntakeDefinition.academic_year == req.academic_year
        )
        intake_obj = (await db.execute(intake_stmt)).scalars().first()
        
        # Norm Info
        from app.modules.requirements.norm_service import resolve_norm as svc_resolve_norm
        from app.modules.requirements.norms_service import derive_course_category
        from app.modules.requirements.norm_constants import CourseCategory
        
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
            
        norm = await svc_resolve_norm(req.institution_id, req.academic_year, course_cat, db)
        
        # Faculty List (with age approx)
        from datetime import date
        faculty_items, _, _, _ = await self.service.get_faculty_list(db, req.institution_id, req.course_id, req.academic_year)
        
        def _get_age(dob: date):
            if not dob: return "Unknown"
            today = date.today()
            return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

        faculty_list = [
            {
                "designation": f.designation,
                "qualification": f.qualification,
                "specialization": f.specialization,
                "employment_type": f.employment_type,
                "age_approx": _get_age(f.date_of_birth)
            } for f in faculty_items
        ]
        
        # 3. Construct AI Context
        norm_info = {
            "faculty_student_ratio": norm.faculty_student_ratio,
            "workload_hours_per_week": norm.workload_hours_per_week,
            "min_qualification": norm.min_qualification,
            "grade_requirement": norm.grade_requirement,
            "max_age": norm.max_age
        }
        
        intake_info = {
            "approved_seats": intake_obj.approved_seats if intake_obj else 0,
            "actual_admitted": intake_obj.actual_admitted if intake_obj else 0
        }
        
        ai_payload = {
            "institution_name": inst_obj.name if inst_obj else "Unknown Institution",
            "course_name": course_obj.name if course_obj else "Unknown Course",
            "required_faculty": assessment.required_count,
            "existing_faculty_count": assessment.effective_existing,
            "suggested_vacancy": assessment.suggested_vacancy
        }
        
        # 4. Call AI Service (OpenAI Integration)
        ai_result = await self.ai_service.analyze(ai_payload, faculty_list, history=None, norm_info=norm_info, intake_info=intake_info)
        
        # 5. Log & Return
        from app.api.requirements import log_audit
        await log_audit(db, "VacancyAssessment", assessment.id, "AI_VACANCY_SUGGESTED", current_user.id, {
            "ai_suggested": ai_result.get("ai_suggested_vacancy"),
            "justification": ai_result.get("justification")
        })
        await db.commit()

        return {
            "status": "success", 
            "data": {
                "system_vacancy": assessment.suggested_vacancy,
                "ai_analysis": ai_result
            }
        }

    async def get_assessment(self, db: AsyncSession, current_user: User, institution_id: int, course_id: int, academic_year: str):
        # We can reuse the suggest logic to fetch or create a basic one
        # For this specific endpoint, we fetch the existing one with counts
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.models.vacancy_assessment import VacancyAssessment
        
        stmt = select(VacancyAssessment).filter(
            VacancyAssessment.institution_id == institution_id,
            VacancyAssessment.course_id == course_id,
            VacancyAssessment.academic_year == academic_year
        ).options(selectinload(VacancyAssessment.anomalies))
        result = await db.execute(stmt)
        assessment = result.scalars().first()
        
        if not assessment:
            return {"status": "success", "data": None}

        # Calculate counts for schema
        high_unack = len([a for a in assessment.anomalies if a.severity == "HIGH" and not a.is_acknowledged])
        
        return {
            "status": "success", 
            "data": {
                **assessment.__dict__,
                "anomaly_count": len(assessment.anomalies),
                "unacknowledged_high_count": high_unack,
                "anomalies": assessment.anomalies
            }
        }

    async def confirm_vacancy(self, db: AsyncSession, current_user: User, institution_id: int, course_id: int, academic_year: str, req: VacancyConfirmRequest):
        assessment = await self.service.confirm_vacancy(db, current_user.id, institution_id, course_id, academic_year, req)
        return {"status": "success", "data": assessment}

    async def acknowledge_anomaly(self, db: AsyncSession, current_user: User, anomaly_id: UUID, req: AnomalyAcknowledgeRequest):
        anomaly = await self.service.acknowledge_anomaly(db, current_user.id, anomaly_id, req.remarks)
        return {"status": "success", "data": anomaly}
