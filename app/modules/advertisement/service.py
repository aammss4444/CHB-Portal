from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional, List
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.advertisement import Advertisement, AdvertisementAction, AdvertisementStatus
from app.models.advertisement_audit import AdvertisementAudit
from app.models.advertisement_template import AdvertisementTemplate
from app.models.audit import AuditLog
from app.models.institution import Course, Institution
from app.models.norm import Norm
from app.models.published_advertisement import PublishedAdvertisement
from app.models.user import RoleEnum, User
from app.models.vacancy_assessment import VacancyAssessment
from app.dependencies.institution_scope import verify_institution_access
from app.modules.advertisement.schemas import (
    AdvertisementApproveRequest,
    AdvertisementGenerateRequest,
    AdvertisementUpdateRequest,
)
from app.modules.advertisement.template_engine import TemplateRenderError, render_advertisement


class AdvertisementService:
    """Business logic for Step 3 advertisement lifecycle."""

    @staticmethod
    def _raise_error(status_code: int, code: str, message: str) -> None:
        raise HTTPException(status_code=status_code, detail={"code": code, "message": message})

    @staticmethod
    def _audit_entity_id(ad_id: UUID) -> str:
        return str(ad_id)

    @staticmethod
    def _validate_date_range(start_date: date, end_date: date) -> None:
        if end_date <= start_date:
            AdvertisementService._raise_error(
                status_code=400,
                code="INVALID_DATE_RANGE",
                message="application_end_date must be greater than application_start_date",
            )

    @staticmethod
    def _status_value(ad: Advertisement) -> str:
        return ad.status.value if isinstance(ad.status, AdvertisementStatus) else str(ad.status)

    async def _assert_principal_scope(self, current_user: User, institution_id: int) -> None:
        try:
            await verify_institution_access(institution_id, current_user)
        except HTTPException as exc:
            if exc.status_code == 403 and current_user.role == RoleEnum.PRINCIPAL:
                self._raise_error(
                    status_code=403,
                    code="UNAUTHORIZED_INSTITUTION",
                    message="You do not have access to this institution's data",
                )
            raise

    async def assert_institution_scope(self, current_user: User, institution_id: int) -> None:
        await self._assert_principal_scope(current_user, institution_id)

    async def _write_audit(
        self,
        db: AsyncSession,
        ad_id: UUID,
        action: AdvertisementAction,
        user_id: int,
        remarks: Optional[str] = None,
        old_value: Optional[dict[str, Any]] = None,
        new_value: Optional[dict[str, Any]] = None,
    ) -> None:
        """Write both advertisement_audit and global audit_logs records."""
        db.add(
            AdvertisementAudit(
                advertisement_id=ad_id,
                action=action.value,
                performed_by=user_id,
                remarks=remarks,
            )
        )
        db.add(
            AuditLog(
                entity_name="Advertisement",
                entity_id=self._audit_entity_id(ad_id),
                action=action.value,
                user_id=user_id,
                old_value=old_value,
                new_value=new_value,
            )
        )

    async def _get_advertisement_or_404(self, db: AsyncSession, ad_id: UUID) -> Advertisement:
        """Fetch advertisement by ID or raise a not found error."""
        stmt = (
            select(Advertisement)
            .where(Advertisement.id == ad_id)
            .options(selectinload(Advertisement.audit_trail))
        )
        ad = (await db.execute(stmt)).scalars().first()
        if not ad:
            raise HTTPException(
                status_code=404,
                detail={"code": "ADVERTISEMENT_NOT_FOUND", "message": "Advertisement not found"},
            )
        return ad

    async def _load_audit_trail(self, db: AsyncSession, ad: Advertisement) -> Advertisement:
        """Audit trail is now loaded via selectinload in _get_advertisement_or_404."""
        return ad

    async def generate_advertisement(
        self,
        db: AsyncSession,
        current_user: User,
        req: AdvertisementGenerateRequest,
    ) -> Advertisement:
        """Generate a new DRAFT advertisement from a CONFIRMED vacancy assessment."""
        self._validate_date_range(req.application_start_date, req.application_end_date)

        assessment_row = (
            await db.execute(
                select(VacancyAssessment, Institution.name, Course.name)
                .join(Institution, Institution.id == VacancyAssessment.institution_id)
                .join(Course, Course.id == VacancyAssessment.course_id)
                .where(VacancyAssessment.id == req.assessment_id)
            )
        ).first()

        if not assessment_row:
            raise HTTPException(
                status_code=404,
                detail={"code": "ASSESSMENT_NOT_FOUND", "message": "Vacancy assessment not found"},
            )

        assessment, institution_name, course_name = assessment_row
        await self._assert_principal_scope(current_user, assessment.institution_id)

        if assessment.status != "CONFIRMED":
            self._raise_error(
                status_code=400,
                code="ASSESSMENT_NOT_CONFIRMED",
                message="Assessment must be CONFIRMED before generating advertisement",
            )

        duplicate = (
            await db.execute(
                select(Advertisement.id).where(
                    and_(
                        Advertisement.institution_id == assessment.institution_id,
                        Advertisement.course_id == assessment.course_id,
                        Advertisement.academic_year == assessment.academic_year,
                        Advertisement.status.in_(
                            [
                                AdvertisementStatus.DRAFT.value,
                                AdvertisementStatus.REVIEW.value,
                                AdvertisementStatus.APPROVED.value,
                                AdvertisementStatus.PUBLISHED.value,
                            ]
                        ),
                    )
                )
            )
        ).first()
        if duplicate:
            self._raise_error(
                status_code=409,
                code="ADVERTISEMENT_ALREADY_EXISTS",
                message="An active advertisement already exists for this institution, Course, and academic year",
            )

        content_en = req.content_en
        content_mr = req.content_mr

        if not content_en or not content_mr:
            # Use hardcoded templates exclusively as per requirements
            en_body = "Advertisement for CHB faculty positions\nInstitution: {{institution_name}}\nCourse: {{course_name}}\nVacancies: {{vacancy_count}}\nAcademic Year: {{academic_year}}\nDesignation: {{designation}}\nQualification: {{qualification}}\nLast Date to Apply: {{application_deadline}}\n"
            mr_body = "सीएचबी जाहिरात\nसंस्था: {{institution_name}}\nशाखा: {{course_name}}\nरिक्त पदे: {{vacancy_count}}\nशैक्षणिक वर्ष: {{academic_year}}\nपदनाम: {{designation}}\nपात्रता: {{qualification}}\nअर्जाची अंतिम तारीख: {{application_deadline}}\n"
            
            tpl_en = AdvertisementTemplate(language="EN", template_body=en_body, name="HARDCODED_EN")
            tpl_mr = AdvertisementTemplate(language="MR", template_body=mr_body, name="HARDCODED_MR")

            # 5. Render Content
            context = {
                "institution_name": institution_name,
                "course_name": course_name,
                "vacancy_count": assessment.confirmed_vacancy,
                "academic_year": assessment.academic_year,
                "application_deadline": req.application_end_date.strftime("%d %B %Y"),
                "designation": "Clock Hour Basis Lecturer",
                "qualification": req.qualification_requirements,
                "required_documents": req.required_documents,
                "important_instructions": req.important_instructions,
                "interview_venue": req.interview_venue,
            }

            try:
                if not content_en:
                    content_en = render_advertisement(tpl_en.template_body, context)
                if not content_mr:
                    content_mr = render_advertisement(tpl_mr.template_body, context)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Template rendering failed: {str(e)}")

        # 6. Save
        ad = Advertisement(
            assessment_id=assessment.id,
            institution_id=assessment.institution_id,
            course_id=assessment.course_id,
            academic_year=assessment.academic_year,
            vacancy_count=assessment.confirmed_vacancy,
            qualification_requirements=req.qualification_requirements,
            required_documents=req.required_documents,
            important_instructions=req.important_instructions,
            interview_venue=req.interview_venue,
            content_en=req.content_en if req.content_en else content_en,
            content_mr=req.content_mr if req.content_mr else content_mr,
            status=AdvertisementStatus.DRAFT.value,
            application_start_date=req.application_start_date,
            application_end_date=req.application_end_date,
            created_by=current_user.id,
        )
        db.add(ad)
        await db.flush()

        await self._write_audit(
            db=db,
            ad_id=ad.id,
            action=AdvertisementAction.GENERATED,
            user_id=current_user.id,
            new_value={
                "status": AdvertisementStatus.DRAFT.value,
                "application_start_date": str(req.application_start_date),
                "application_end_date": str(req.application_end_date),
            },
        )
        await db.commit()

        return await self.get_advertisement(db, ad.id, current_user)

    async def get_advertisement(self, db: AsyncSession, ad_id: UUID, current_user: User) -> Advertisement:
        """Return one advertisement with its audit trail after institution scope checks."""
        ad = await self._get_advertisement_or_404(db, ad_id)
        await self._assert_principal_scope(current_user, ad.institution_id)
        return await self._load_audit_trail(db, ad)

    async def update_advertisement(
        self,
        db: AsyncSession,
        ad_id: UUID,
        current_user: User,
        req: AdvertisementUpdateRequest,
    ) -> Advertisement:
        """Edit mutable advertisement fields when status is DRAFT or REJECTED only."""
        self._validate_date_range(req.application_start_date, req.application_end_date)
        ad = await self._get_advertisement_or_404(db, ad_id)
        await self._assert_principal_scope(current_user, ad.institution_id)

        current_status = self._status_value(ad)
        if current_status not in {AdvertisementStatus.DRAFT.value, AdvertisementStatus.REJECTED.value}:
            self._raise_error(
                status_code=403,
                code="ADVERTISEMENT_IMMUTABLE",
                message=f"Cannot edit advertisement in {current_status} status",
            )

        old_values = {
            "content_en": ad.content_en,
            "content_mr": ad.content_mr,
            "application_start_date": str(ad.application_start_date),
            "application_end_date": str(ad.application_end_date),
        }

        ad.content_en = req.content_en
        ad.content_mr = req.content_mr
        ad.application_start_date = req.application_start_date
        ad.application_end_date = req.application_end_date
        
        if req.qualification_requirements is not None:
            ad.qualification_requirements = req.qualification_requirements
        if req.required_documents is not None:
            ad.required_documents = req.required_documents
        if req.important_instructions is not None:
            ad.important_instructions = req.important_instructions
        if req.interview_venue is not None:
            ad.interview_venue = req.interview_venue

        await self._write_audit(
            db=db,
            ad_id=ad.id,
            action=AdvertisementAction.EDITED,
            user_id=current_user.id,
            old_value=old_values,
            new_value={
                "content_en": req.content_en,
                "content_mr": req.content_mr,
                "application_start_date": str(req.application_start_date),
                "application_end_date": str(req.application_end_date),
            },
        )
        await db.commit()
        return await self.get_advertisement(db, ad.id, current_user)

    async def submit_advertisement(self, db: AsyncSession, ad_id: UUID, current_user: User) -> Advertisement:
        """Move a DRAFT/REJECTED advertisement to REVIEW after validations pass."""
        ad = await self._get_advertisement_or_404(db, ad_id)
        await self._assert_principal_scope(current_user, ad.institution_id)

        current_status = self._status_value(ad)
        if current_status not in {AdvertisementStatus.DRAFT.value, AdvertisementStatus.REJECTED.value}:
            self._raise_error(
                status_code=400,
                code="INVALID_STATUS_TRANSITION",
                message="Only advertisements in DRAFT or REJECTED can be submitted",
            )

        if not ad.application_start_date or not ad.application_end_date:
            self._raise_error(
                status_code=400,
                code="INVALID_DATE_RANGE",
                message="application_start_date and application_end_date are required before submission",
            )

        self._validate_date_range(ad.application_start_date, ad.application_end_date)



        if not ad.content_en.strip() or not ad.content_mr.strip():
            self._raise_error(
                status_code=400,
                code="INVALID_STATUS_TRANSITION",
                message="content_en and content_mr must not be empty",
            )

        ad.status = AdvertisementStatus.REVIEW.value

        await self._write_audit(
            db=db,
            ad_id=ad.id,
            action=AdvertisementAction.SUBMITTED,
            user_id=current_user.id,
            new_value={"status": AdvertisementStatus.REVIEW.value},
        )
        await db.commit()
        return await self.get_advertisement(db, ad.id, current_user)

    async def approve_advertisement(
        self,
        db: AsyncSession,
        ad_id: UUID,
        current_user: User,
        req: AdvertisementApproveRequest,
    ) -> Advertisement:
        """Approve or reject a REVIEW advertisement as ADMIN."""
        ad = await self._get_advertisement_or_404(db, ad_id)
        if self._status_value(ad) != AdvertisementStatus.REVIEW.value:
            self._raise_error(
                status_code=400,
                code="INVALID_STATUS_TRANSITION",
                message="Only advertisements in REVIEW can be approved or rejected",
            )

        if req.action.value == "APPROVE":
            ad.status = AdvertisementStatus.APPROVED.value
            ad.approved_by = current_user.id
            ad.approved_at = datetime.utcnow()
            ad.rejection_reason = None
            await self._write_audit(
                db=db,
                ad_id=ad.id,
                action=AdvertisementAction.APPROVED,
                user_id=current_user.id,
                remarks=req.remarks,
                new_value={"status": AdvertisementStatus.APPROVED.value},
            )
        else:
            if not req.remarks or not req.remarks.strip():
                self._raise_error(
                    status_code=400,
                    code="INVALID_STATUS_TRANSITION",
                    message="remarks are required when rejecting an advertisement",
                )
            ad.status = AdvertisementStatus.REJECTED.value
            ad.rejection_reason = req.remarks.strip()
            await self._write_audit(
                db=db,
                ad_id=ad.id,
                action=AdvertisementAction.REJECTED,
                user_id=current_user.id,
                remarks=ad.rejection_reason,
                new_value={
                    "status": AdvertisementStatus.REJECTED.value,
                    "rejection_reason": ad.rejection_reason,
                },
            )

        await db.commit()
        return await self.get_advertisement(db, ad.id, current_user)

    async def publish_advertisement(self, db: AsyncSession, ad_id: UUID, current_user: User) -> dict[str, str]:
        """Publish an APPROVED advertisement and return a public token + URL."""
        ad = await self._get_advertisement_or_404(db, ad_id)
        if self._status_value(ad) != AdvertisementStatus.APPROVED.value:
            self._raise_error(
                status_code=400,
                code="INVALID_STATUS_TRANSITION",
                message="Cannot publish advertisement before ADMIN approval",
            )

        public_token = str(uuid4())
        while (
            await db.execute(
                select(PublishedAdvertisement.id).where(PublishedAdvertisement.public_token == public_token)
            )
        ).first():
            public_token = str(uuid4())

        db.add(
            PublishedAdvertisement(
                advertisement_id=ad.id,
                public_token=public_token,
                published_by=current_user.id,
            )
        )

        ad.status = AdvertisementStatus.PUBLISHED.value
        ad.published_at = datetime.utcnow()

        await self._write_audit(
            db=db,
            ad_id=ad.id,
            action=AdvertisementAction.PUBLISHED,
            user_id=current_user.id,
            new_value={"status": AdvertisementStatus.PUBLISHED.value, "public_token": public_token},
        )
        await db.commit()

        return {
            "public_token": public_token,
            "public_url": f"/api/advertisements/public/{public_token}",
        }

    async def delete_advertisement(self, db: AsyncSession, ad_id: UUID, current_user: User) -> dict[str, str]:
        """Delete advertisement when it is not published."""
        ad = await self._get_advertisement_or_404(db, ad_id)
        await self._assert_principal_scope(current_user, ad.institution_id)

        current_status = self._status_value(ad)
        if current_status == AdvertisementStatus.PUBLISHED.value:
            self._raise_error(
                status_code=400,
                code="ADVERTISEMENT_IMMUTABLE",
                message="Published advertisements cannot be deleted",
            )

        await db.delete(ad)
        await db.commit()
        return {"message": f"Advertisement {ad_id} deleted successfully"}

    async def get_public_advertisement(self, db: AsyncSession, token: str) -> dict[str, Any]:
        """Return publicly visible advertisement fields using a publish token."""
        row = (
            await db.execute(
                select(
                    Advertisement.content_en,
                    Advertisement.content_mr,
                    Advertisement.vacancy_count,
                    Advertisement.application_start_date,
                    Advertisement.application_end_date,
                    Institution.name.label("institution_name"),
                    Course.name.label("course_name"),
                )
                .select_from(PublishedAdvertisement)
                .join(Advertisement, Advertisement.id == PublishedAdvertisement.advertisement_id)
                .join(Institution, Institution.id == Advertisement.institution_id)
                .join(Course, Course.id == Advertisement.course_id)
                .where(
                    and_(
                        PublishedAdvertisement.public_token == token,
                        PublishedAdvertisement.is_active.is_(True),
                    )
                )
            )
        ).mappings().first()

        if not row:
            raise HTTPException(
                status_code=404,
                detail={"code": "PUBLIC_ADVERTISEMENT_NOT_FOUND", "message": "Public advertisement not found"},
            )

        return {
            "content_en": row["content_en"],
            "content_mr": row["content_mr"],
            "institution_name": row["institution_name"],
            "course_name": row["course_name"],
            "vacancy_count": row["vacancy_count"],
            "application_start_date": row["application_start_date"],
            "application_end_date": row["application_end_date"],
        }

    async def list_published_advertisements(
        self,
        db: AsyncSession,
        institution_id: Optional[int] = None,
        course_id: Optional[int] = None,
        academic_year: Optional[str] = None,
        skip: int = 0,
        limit: int = 10,
    ) -> tuple[List[dict[str, Any]], int]:
        """List all currently PUBLISHED advertisements with optional filters."""
        stmt = (
            select(
                Advertisement.id,
                Institution.name.label("institution_name"),
                Course.name.label("course_name"),
                Advertisement.academic_year,
                Advertisement.vacancy_count,
                Advertisement.application_start_date,
                Advertisement.application_end_date,
            )
            .join(Institution, Institution.id == Advertisement.institution_id)
            .join(Course, Course.id == Advertisement.course_id)
            .where(Advertisement.status == AdvertisementStatus.PUBLISHED.value)
        )

        if institution_id:
            stmt = stmt.where(Advertisement.institution_id == institution_id)
        if course_id:
            stmt = stmt.where(Advertisement.course_id == course_id)
        if academic_year:
            stmt = stmt.where(Advertisement.academic_year == academic_year)

        from sqlalchemy import func
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(Advertisement.published_at.desc())
        if limit > 0:
            stmt = stmt.offset(skip).limit(limit)
        
        rows = (await db.execute(stmt)).mappings().all()
        return [dict(row) for row in rows], total

    async def get_advertisement_meta(self, db: AsyncSession, current_user: User) -> dict[str, Any]:
        institutions_stmt = select(Institution.id, Institution.name)
        if current_user.role == RoleEnum.PRINCIPAL:
            if not current_user.institution_id:
                self._raise_error(403, "UNAUTHORIZED_INSTITUTION", "Principal is not mapped to any institution")
            institutions_stmt = institutions_stmt.where(Institution.id == current_user.institution_id)

        institutions = [
            {"id": row.id, "name": row.name}
            for row in (await db.execute(institutions_stmt.order_by(Institution.name.asc()))).all()
        ]
        institution_ids = [i["id"] for i in institutions]

        courses: list[dict[str, Any]] = []
        if institution_ids:
            course_rows = (
                await db.execute(
                    select(Course.id, Course.name, Course.level)
                    .where(Course.institution_id.in_(institution_ids))
                    .order_by(Course.name.asc())
                )
            ).all()
            courses = [{"id": r.id, "name": r.name, "level": r.level} for r in course_rows]

        latest_norm = (
            await db.execute(
                select(Norm.min_qualification, Norm.faculty_student_ratio).order_by(Norm.id.desc())
            )
        ).first()

        norms = {
            "min_qualification": latest_norm.min_qualification if latest_norm else None,
            "faculty_student_ratio": float(latest_norm.faculty_student_ratio) if latest_norm else None,
        }

        return {
            "institutions": institutions,
            "courses": courses,
            "norms": norms,
            "reservation": {"SC": 13, "ST": 7, "OBC": 19, "EWS": 10},
            "suggested_vacancy": None,
        }

    async def list_advertisements(
        self,
        db: AsyncSession,
        current_user: User,
        skip: int = 0,
        limit: int = 10,
    ) -> tuple[List[Advertisement], int]:
        """List all advertisements with role-based filtering."""
        stmt = select(Advertisement).options(selectinload(Advertisement.audit_trail))
        
        if current_user.role == RoleEnum.PRINCIPAL:
            if not current_user.institution_id:
                return [], 0
            stmt = stmt.where(Advertisement.institution_id == current_user.institution_id)
            
        # Count total
        from sqlalchemy import func
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()
        
        # Paginate and order
        stmt = stmt.order_by(Advertisement.created_at.desc()).offset(skip).limit(limit)
        results = (await db.execute(stmt)).scalars().all()
        
        return list(results), total
