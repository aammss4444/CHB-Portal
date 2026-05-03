from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.models.user import User
from app.modules.advertisement.schemas import (
    AdvertisementApproveRequest,
    AdvertisementGenerateRequest,
    AdvertisementUpdateRequest,
)
from app.modules.advertisement.service import AdvertisementService
from app.modules.advertisement.ai_engine import AdvertisementAIEngine
from app.modules.advertisement.ai_service import AdvertisementAIService
from app.schemas.advertisement_ai import AdvertisementAIRequest
from app.modules.requirements.norms_service import derive_course_category, resolve_norm, NormResolutionError


class AdvertisementController:
    def __init__(self) -> None:
        self.service = AdvertisementService()
        self.ai_engine = AdvertisementAIEngine()
        self.ai_service = AdvertisementAIService(self.ai_engine)

    async def generate_advertisement(self, db: AsyncSession, current_user: User, req: AdvertisementGenerateRequest):
        # 1. Generate template-based ad (Deterministic)
        ad = await self.service.generate_advertisement(db, current_user, req)
        
        # 2. Fetch context for AI
        from sqlalchemy import select
        from app.models.institution import Institution, Course
        inst = (await db.execute(select(Institution).filter(Institution.id == ad.institution_id))).scalars().first()
        course_obj = (await db.execute(select(Course).filter(Course.id == ad.course_id))).scalars().first()
        
        ai_payload = {
            "institution_name": inst.name if inst else "Unknown",
            "course_name": course_obj.name if course_obj else "Unknown",
            "vacancy_count": ad.vacancy_count,
            "qualification": ad.qualification_requirements,
            "required_documents": ad.required_documents,
            "important_instructions": ad.important_instructions,
            "interview_venue": ad.interview_venue,
            "designation": "Clock Hour Basis Lecturer",
            "deadline": ad.application_end_date.isoformat() if ad.application_end_date else None,
            "language_versions": {
                "english": ad.content_en,
                "marathi": ad.content_mr
            }
        }
        
        # 3. Call AI Service
        ai_result = await self.ai_service.generate(
            {
                "institution_name": ai_payload["institution_name"],
                "course_name": ai_payload["course_name"],
                "course_level": course_obj.level if course_obj else "UG",
                "vacancy_count": ai_payload["vacancy_count"],
                "qualification": ai_payload["qualification"],
                "reservation": {"SC": 13, "ST": 7, "OBC": 19, "EWS": 10},
                "deadline": ai_payload["deadline"],
                "application_mode": "Walk-in",
            }
        )
        
        return {
            "status": "success",
            "data": {
                "template_ad": ad,
                "ai_enhanced_ad": {
                    "status": "OK" if not ai_result.get("issues") else "NEEDS_IMPROVEMENT",
                    "enhanced_ad": {
                        "english": ai_result.get("english", ""),
                        "marathi": ai_result.get("marathi", ""),
                    },
                    "issues": ai_result.get("issues", []),
                    "suggestions": [],
                    "compliance_flags": [],
                    "confidence_score": ai_result.get("confidence_score", 0.0),
                },
            }
        }

    async def get_advertisement(self, db: AsyncSession, ad_id: UUID, current_user: User):
        data = await self.service.get_advertisement(db, ad_id, current_user)
        return {"status": "success", "data": data}

    async def update_advertisement(self, db: AsyncSession, ad_id: UUID, current_user: User, req: AdvertisementUpdateRequest):
        data = await self.service.update_advertisement(db, ad_id, current_user, req)
        return {"status": "success", "data": data}

    async def submit_advertisement(self, db: AsyncSession, ad_id: UUID, current_user: User):
        # 1. Perform submission logic
        ad = await self.service.submit_advertisement(db, ad_id, current_user)
        
        # 2. AI Quality Check (Warning only)
        from sqlalchemy import select
        from app.models.institution import Institution, Course
        inst = (await db.execute(select(Institution).filter(Institution.id == ad.institution_id))).scalars().first()
        course_obj = (await db.execute(select(Course).filter(Course.id == ad.course_id))).scalars().first()
        
        ai_payload = {
            "institution_name": inst.name if inst else "Unknown",
            "course_name": course_obj.name if course_obj else "Unknown",
            "vacancy_count": ad.vacancy_count,
            "qualification": ad.qualification_requirements,
            "required_documents": ad.required_documents,
            "important_instructions": ad.important_instructions,
            "interview_venue": ad.interview_venue,
            "designation": "Clock Hour Basis Lecturer",
            "deadline": ad.application_end_date.isoformat() if ad.application_end_date else None,
            "language_versions": {
                "english": ad.content_en,
                "marathi": ad.content_mr
            }
        }
        
        ai_result = await self.ai_service.generate(
            {
                "institution_name": ai_payload["institution_name"],
                "course_name": ai_payload["course_name"],
                "course_level": course_obj.level if course_obj else "UG",
                "vacancy_count": ai_payload["vacancy_count"],
                "qualification": ai_payload["qualification"],
                "reservation": {"SC": 13, "ST": 7, "OBC": 19, "EWS": 10},
                "deadline": ai_payload["deadline"],
                "application_mode": "Walk-in",
            }
        )
        warning = None
        if ai_result.get("issues"):
            warning = "AI analysis indicates this advertisement needs improvement in clarity or compliance. Please review suggestions before final approval."
            
        return {"status": "success", "data": ad, "warning": warning}

    async def approve_advertisement(self, db: AsyncSession, ad_id: UUID, current_user: User, req: AdvertisementApproveRequest):
        data = await self.service.approve_advertisement(db, ad_id, current_user, req)
        return {"status": "success", "data": data}

    async def publish_advertisement(self, db: AsyncSession, ad_id: UUID, current_user: User):
        data = await self.service.publish_advertisement(db, ad_id, current_user)
        return {"status": "success", "data": data}

    async def delete_advertisement(self, db: AsyncSession, ad_id: UUID, current_user: User):
        data = await self.service.delete_advertisement(db, ad_id, current_user)
        return {"status": "success", "data": data}

    async def get_public_advertisement(self, db: AsyncSession, token: str):
        data = await self.service.get_public_advertisement(db, token)
        return {"status": "success", "data": data}

    async def list_published_advertisements(
        self,
        db: AsyncSession,
        institution_id: Optional[int] = None,
        course_id: Optional[int] = None,
        academic_year: Optional[str] = None,
        skip: int = 0,
        limit: int = 10,
    ):
        data, total = await self.service.list_published_advertisements(db, institution_id, course_id, academic_year, skip, limit)
        import math
        return {
            "status": "success",
            "data": data,
            "total": total,
            "page": (skip // limit) + 1 if limit > 0 else 1,
            "limit": limit,
            "total_pages": math.ceil(total / limit) if limit > 0 else 0
        }

    async def get_advertisement_meta(self, db: AsyncSession, current_user: User):
        data = await self.service.get_advertisement_meta(db, current_user)
        return {"status": "success", "data": data}

    async def generate_advertisement_ai(self, db: AsyncSession, current_user: User, req: AdvertisementAIRequest):
        from sqlalchemy import select
        from app.models.institution import Institution, Course
        from app.models.norm import Norm
        from app.models.vacancy_assessment import VacancyAssessment

        await self.service.assert_institution_scope(current_user, req.institution_id)
        inst = (await db.execute(select(Institution).where(Institution.id == req.institution_id))).scalars().first()
        course_obj = (await db.execute(select(Course).where(Course.id == req.course_id))).scalars().first()
        if not inst or not course_obj:
            raise HTTPException(
                status_code=404,
                detail={"code": "INVALID_SCOPE_INPUT", "message": "Institution or Course not found"},
            )

        course_category = derive_course_category(course_obj.name, course_obj.level)
        try:
            norm = await resolve_norm(db, req.academic_year, course_category)
        except NormResolutionError:
            norm = None
        qualification = (norm.min_qualification if norm and norm.min_qualification else "As per AICTE/DTE norms")

        assessment = (
            await db.execute(
                select(VacancyAssessment)
                .where(
                    VacancyAssessment.institution_id == req.institution_id,
                    VacancyAssessment.course_id == req.course_id,
                )
                .order_by(VacancyAssessment.created_at.desc())
            )
        ).scalars().first()
        suggested_vacancy = assessment.suggested_vacancy if assessment else req.vacancy_count

        ai_payload = {
            "institution_name": inst.name,
            "course_name": course_obj.name,
            "course_level": course_obj.level,
            "vacancy_count": req.vacancy_count or suggested_vacancy,
            "qualification": qualification,
            "reservation": {"SC": 13, "ST": 7, "OBC": 19, "EWS": 10},
            "deadline": req.deadline,
            "application_mode": req.application_mode or "Walk-in",
        }

        ai_result = await self.ai_service.generate(ai_payload)
        ai_result.setdefault("sections_present", {})
        template_ad = {
            "title_en": f"CHB Lecturer Recruitment - {inst.name}",
            "title_mr": f"CHB व्याख्याता भरती - {inst.name}",
            "institution": inst.name,
            "course": course_obj.name,
            "vacancy_count": ai_payload["vacancy_count"],
            "qualification": qualification,
            "reservation": ai_payload["reservation"],
            "deadline": req.deadline,
            "application_mode": req.application_mode or "Walk-in",
        }
        return {"status": "success", "data": {"template_ad": template_ad, "ai_generated_ad": ai_result}}

    async def get_recruitment_context(self, db: AsyncSession, current_user: User, institution_id: int, course_id: int, academic_year: str):
        """
        Enterprise endpoint: Fetches linked Step 1 + Step 2 data for Step 3 (Ad Generation).
        Returns institution, course, qualification norms, faculty requirement, and vacancy assessment.
        """
        from sqlalchemy import select
        from app.models.institution import Institution, Course
        from app.models.intake import IntakeDefinition
        from app.models.faculty_req import FacultyRequirement
        from app.models.vacancy_assessment import VacancyAssessment
        from app.models.norm import Norm

        await self.service.assert_institution_scope(current_user, institution_id)

        # Institution
        inst = (await db.execute(select(Institution).where(Institution.id == institution_id))).scalars().first()
        if not inst:
            raise HTTPException(status_code=404, detail={"code": "INSTITUTION_NOT_FOUND", "message": "Institution not found"})

        # Course
        course_obj = (await db.execute(select(Course).where(Course.id == course_id))).scalars().first()
        if not course_obj:
            raise HTTPException(status_code=404, detail={"code": "COURSE_NOT_FOUND", "message": "Course not found"})

        # Step 1: Intake + Faculty Requirement
        intake = (await db.execute(
            select(IntakeDefinition).where(
                IntakeDefinition.course_id == course_id,
                IntakeDefinition.academic_year == academic_year
            )
        )).scalars().first()

        requirement = None
        if intake:
            requirement = (await db.execute(
                select(FacultyRequirement).where(FacultyRequirement.intake_id == intake.id)
            )).scalars().first()

        # Step 1: Norms (qualification)
        course_category = derive_course_category(course_obj.name, course_obj.level)
        try:
            norm = await resolve_norm(db, academic_year, course_category)
        except NormResolutionError:
            norm = None

        qualification = norm.min_qualification if norm and norm.min_qualification else "As per AICTE/DTE norms"
        faculty_student_ratio = float(norm.faculty_student_ratio) if norm else None

        # Step 2: Vacancy Assessment
        assessment = (await db.execute(
            select(VacancyAssessment).where(
                VacancyAssessment.institution_id == institution_id,
                VacancyAssessment.course_id == course_id,
                VacancyAssessment.academic_year == academic_year
            )
        )).scalars().first()

        # Build response
        step1 = {
            "status": "complete" if requirement else "pending",
            "approved_seats": intake.approved_seats if intake else None,
            "actual_admitted": intake.actual_admitted if intake else None,
            "computed_required_count": requirement.computed_required_count if requirement else None,
            "formula_breakdown": requirement.formula_breakdown if requirement else None,
        }

        step2 = {
            "status": assessment.status if assessment else "pending",
            "required_count": assessment.required_count if assessment else None,
            "total_existing": assessment.total_existing if assessment else None,
            "effective_existing": assessment.effective_existing if assessment else None,
            "suggested_vacancy": assessment.suggested_vacancy if assessment else None,
            "confirmed_vacancy": assessment.confirmed_vacancy if assessment else None,
            "assessment_id": str(assessment.id) if assessment else None,
        }

        return {
            "status": "success",
            "data": {
                "institution": {"id": inst.id, "name": inst.name, "code": inst.code, "district": inst.district, "type": inst.type},
                "course": {"id": course_obj.id, "name": course_obj.name, "level": course_obj.level},
                "academic_year": academic_year,
                "norms": {
                    "min_qualification": qualification,
                    "faculty_student_ratio": faculty_student_ratio,
                    "max_age": norm.max_age if norm else None,
                    "workload_hours_per_week": norm.workload_hours_per_week if norm else None,
                },
                "reservation": {"SC": 13, "ST": 7, "OBC": 19, "EWS": 10},
                "step1_requirement": step1,
                "step2_vacancy": step2,
                "can_generate_ad": assessment is not None and assessment.status == "CONFIRMED",
                "vacancy_count": assessment.confirmed_vacancy if assessment and assessment.status == "CONFIRMED" else None,
            }
        }
