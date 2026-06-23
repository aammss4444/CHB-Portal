import logging
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

logger = logging.getLogger(__name__)

class AdvertisementController:
    def __init__(self) -> None:
        self.service = AdvertisementService()
        self.ai_engine = AdvertisementAIEngine()
        self.ai_service = AdvertisementAIService(self.ai_engine)

    async def generate_advertisement(self, db: AsyncSession, current_user: User, req: AdvertisementGenerateRequest):
        try:
            ad = await self.service.generate_advertisement(db, current_user, req)
            from app.modules.advertisement.schemas import AdvertisementResponse
            return {
                "status": "success",
                "data": AdvertisementResponse.model_validate(ad)
            }
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            with open('D:/chb2/CHB/backend/scratch/traceback.txt', 'w') as f:
                traceback.print_exc(file=f)
            logger.exception("CRITICAL: generate_advertisement crashed")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_advertisement(self, db: AsyncSession, ad_id: UUID, current_user: User):
        try:
            data = await self.service.get_advertisement(db, ad_id, current_user)
            return {"status": "success", "data": data}
        except Exception as e:
            logger.exception(f"Error getting advertisement {ad_id}")
            raise HTTPException(status_code=500, detail=str(e))

    async def generate_advertisement_ai(self, db: AsyncSession, current_user: User, req: AdvertisementAIRequest):
        """
        Pure AI generation endpoint. Does NOT save to DB yet.
        Used for previewing before finalizing.
        """
        try:
            from sqlalchemy import select
            from app.models.institution import Institution, Course
            
            await self.service.assert_institution_scope(current_user, req.institution_id)
            
            inst = (await db.execute(select(Institution).filter(Institution.id == req.institution_id))).scalars().first()
            course_obj = (await db.execute(select(Course).filter(Course.id == req.course_id))).scalars().first()
            
            # 1. Fetch norms for qualification context
            course_category = derive_course_category(course_obj.name, course_obj.level)
            try:
                norm = await resolve_norm(db, req.academic_year, course_category)
            except NormResolutionError:
                norm = None
            
            qualification = norm.min_qualification if norm and norm.min_qualification else "As per AICTE/DTE norms"

            # 2. Call AI Service
            ai_result = await self.ai_service.generate(
                {
                    "institution_name": inst.name if inst else "Unknown",
                    "course_name": course_obj.name if course_obj else "Unknown",
                    "course_level": course_obj.level if course_obj else "UG",
                    "vacancy_count": req.vacancy_count,
                    "qualification": qualification,
                    "reservation": {"SC": 13, "ST": 7, "OBC": 19, "EWS": 10},
                    "deadline": req.deadline,
                    "application_mode": req.application_mode,
                }
            )
            
            from app.modules.advertisement.schemas import AdvertisementAIResponse
            return {
                "status": "success",
                "data": {
                    "template_ad": {}, # No template yet as this is pre-save
                    "ai_generated_ad": AdvertisementAIResponse.model_validate(ai_result)
                }
            }
        except Exception as e:
            logger.exception("CRITICAL: generate_advertisement_ai crashed")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_recruitment_context(self, db: AsyncSession, current_user: User, institution_id: int, course_id: int, academic_year: str):
        try:
            from sqlalchemy import select
            from app.models.institution import Institution, Course
            from app.models.intake import IntakeDefinition
            from app.models.faculty_req import FacultyRequirement
            from app.models.vacancy_assessment import VacancyAssessment
            from app.models.advertisement import Advertisement

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

            # Step 3: Existing Advertisement
            ad = (await db.execute(
                select(Advertisement).where(
                    Advertisement.institution_id == institution_id,
                    Advertisement.course_id == course_id,
                    Advertisement.academic_year == academic_year,
                    Advertisement.status != "DELETED"
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
                    "can_generate_ad": assessment is not None and assessment.status == "CONFIRMED",
                    "vacancy_count": assessment.confirmed_vacancy if assessment else 0,
                    "norms": {
                        "min_qualification": qualification,
                        "faculty_student_ratio": faculty_student_ratio,
                        "max_age": norm.max_age if norm else None,
                        "workload_hours_per_week": norm.workload_hours_per_week if norm else None,
                    },
                    "reservation": {"SC": 13, "ST": 7, "OBC": 19, "EWS": 10},
                    "step1_requirement": step1,
                    "step2_vacancy": step2,
                    "step3_advertisement": {
                        "id": str(ad.id) if ad else None,
                        "status": ad.status if ad else "pending",
                        "vacancy_count": ad.vacancy_count if ad else None
                    }
                }
            }
        except Exception as e:
            logger.exception("CRITICAL: get_recruitment_context crashed")
            raise HTTPException(status_code=500, detail=str(e))

    async def update_advertisement(self, db: AsyncSession, ad_id: UUID, current_user: User, req: AdvertisementUpdateRequest):
        data = await self.service.update_advertisement(db, ad_id, current_user, req)
        return {"status": "success", "data": data}

    async def submit_advertisement(self, db: AsyncSession, ad_id: UUID, current_user: User):
        ad = await self.service.submit_advertisement(db, ad_id, current_user)
        return {"status": "success", "data": ad}

    async def approve_advertisement(self, db: AsyncSession, ad_id: UUID, current_user: User, req: AdvertisementApproveRequest):
        ad = await self.service.approve_advertisement(db, ad_id, current_user, req)
        return {"status": "success", "data": ad}

    async def publish_advertisement(self, db: AsyncSession, ad_id: UUID, current_user: User):
        result = await self.service.publish_advertisement(db, ad_id, current_user)
        return {"status": "success", "data": result}

    async def delete_advertisement(self, db: AsyncSession, ad_id: UUID, current_user: User):
        data = await self.service.delete_advertisement(db, ad_id, current_user)
        return {"status": "success", "data": data}

    async def list_advertisements(self, db: AsyncSession, current_user: User, skip: int = 0, limit: int = 10):
        try:
            items, total = await self.service.list_advertisements(db, current_user, skip, limit)
            from app.modules.advertisement.schemas import AdvertisementResponse
            return {
                "status": "success",
                "data": [AdvertisementResponse.model_validate(item) for item in items],
                "total": total
            }
        except Exception as e:
            logger.exception("Error listing advertisements")
            raise HTTPException(status_code=500, detail=str(e))

    async def list_published_advertisements(self, db: AsyncSession, institution_id: Optional[int], course_id: Optional[int], academic_year: Optional[str], skip: int, limit: int):
        try:
            items, total = await self.service.list_published_advertisements(db, institution_id, course_id, academic_year, skip, limit)
            return {
                "status": "success",
                "data": items, # Service already returns dictionaries/objects for published list
                "total": total
            }
        except Exception as e:
            logger.exception("Error listing published advertisements")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_advertisement_meta(self, db: AsyncSession, current_user: User):
        try:
            data = await self.service.get_advertisement_meta(db, current_user)
            return {"status": "success", "data": data}
        except Exception as e:
            logger.exception("Error getting advertisement meta")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_public_advertisement(self, db: AsyncSession, public_token: str):
        try:
            data = await self.service.get_public_advertisement(db, public_token)
            return {"status": "success", "data": data}
        except Exception as e:
            logger.exception(f"Error getting public advertisement for token {public_token}")
            raise HTTPException(status_code=500, detail=str(e))
