from __future__ import annotations

from datetime import datetime, date, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies.institution_scope import verify_institution_access
from app.models.advertisement import Advertisement, AdvertisementStatus
from app.models.application import Application, ApplicationStatus
from app.models.application_document import ApplicationDocument
from app.models.audit import AuditLog
from app.models.candidate import Candidate
from app.models.institution import Course, Institution
from app.models.user import RoleEnum, User
from app.models.shortlisted_candidate import ShortlistedCandidate
from app.modules.application.document_validator import run_document_validation_task
from app.modules.application.schemas import (
    ApplicationCreateRequest,
    ApplicationSubmitRequest,
    ApplicationAction,
    ApplicationActionRequest,
)
from app.services.storage_service import save_file


ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/tiff"}
MAX_FILE_SIZE_KB = 2048
REQUIRED_DOCUMENTS = {"PHOTO", "SIGNATURE", "AADHAR", "DEGREE_CERTIFICATE", "MARKSHEET"}
ALLOWED_DOCUMENT_TYPES = {
    "PHOTO",
    "SIGNATURE",
    "AADHAR",
    "PAN",
    "DEGREE_CERTIFICATE",
    "MARKSHEET",
    "EXPERIENCE_LETTER",
    "CASTE_CERTIFICATE",
    "NOC",
    "PUBLICATION_PROOF",
    "OTHER",
}


class ApplicationService:
    @staticmethod
    def _raise_error(status_code: int, code: str, message: str) -> None:
        raise HTTPException(status_code=status_code, detail={"code": code, "message": message})

    @staticmethod
    def _entity_id_from_uuid(value: UUID) -> str:
        return str(value)

    async def _write_audit(
        self,
        db: AsyncSession,
        entity_name: str,
        entity_id: str,
        action: str,
        user_id: int,
        old_value: Optional[dict[str, Any]] = None,
        new_value: Optional[dict[str, Any]] = None,
    ) -> None:
        db.add(
            AuditLog(
                entity_name=entity_name,
                entity_id=entity_id,
                action=action,
                user_id=user_id,
                old_value=old_value,
                new_value=new_value,
            )
        )

    async def _get_candidate_by_user(self, db: AsyncSession, user_id: int) -> Optional[Candidate]:
        stmt = select(Candidate).where(Candidate.user_id == user_id)
        return (await db.execute(stmt)).scalars().first()

    async def _get_candidate_or_404(self, db: AsyncSession, user_id: int) -> Candidate:
        candidate = await self._get_candidate_by_user(db, user_id)
        if not candidate:
            self._raise_error(404, "UNAUTHORIZED_ACCESS", "Candidate profile not found for current user")
        return candidate

    async def _get_application_for_candidate(
        self, db: AsyncSession, application_id: UUID, candidate_id: UUID
    ) -> Application:
        app = (
            await db.execute(
                select(Application).where(
                    and_(Application.id == application_id, Application.candidate_id == candidate_id)
                )
            )
        ).scalars().first()
        if not app:
            self._raise_error(403, "UNAUTHORIZED_ACCESS", "You do not have access to this application.")
        return app

    async def assert_application_view_access(self, db: AsyncSession, current_user: User, application: Application) -> None:
        if current_user.role == RoleEnum.ADMIN:
            return
        if current_user.role == RoleEnum.PRINCIPAL:
            await verify_institution_access(application.institution_id, current_user)
            return
        if current_user.role == RoleEnum.CANDIDATE:
            candidate = await self._get_candidate_or_404(db, current_user.id)
            if application.candidate_id != candidate.id:
                self._raise_error(403, "UNAUTHORIZED_ACCESS", "You do not have access to this application.")
            return
        self._raise_error(403, "UNAUTHORIZED_ACCESS", "Access denied.")

    async def _assert_ad_window_open(self, ad: Advertisement) -> None:
        if ad.status != AdvertisementStatus.PUBLISHED.value:
            self._raise_error(400, "ADVERTISEMENT_CLOSED", "Advertisement is not published.")

        today = date.today()
        if not ad.application_start_date or not ad.application_end_date:
            self._raise_error(400, "ADVERTISEMENT_CLOSED", "Advertisement application dates are not configured.")
        if today < ad.application_start_date or today > ad.application_end_date:
            self._raise_error(400, "ADVERTISEMENT_CLOSED", "Advertisement is outside application window.")

    async def _next_application_number(self, db: AsyncSession) -> str:
        year = datetime.now(timezone.utc).year
        prefix = f"CHB-{year}-"
        last = (
            await db.execute(
                select(Application.application_number)
                .where(Application.application_number.like(f"{prefix}%"))
                .order_by(Application.application_number.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if not last:
            sequence = 1
        else:
            sequence = int(last.split("-")[-1]) + 1
        return f"{prefix}{sequence:05d}"

    async def create_application(
        self, db: AsyncSession, current_user: User, req: ApplicationCreateRequest
    ) -> Application:
        candidate = await self._get_candidate_or_404(db, current_user.id)
        if not candidate.is_profile_complete:
            self._raise_error(400, "PROFILE_INCOMPLETE", "Complete profile before creating application.")

        ad = (
            await db.execute(select(Advertisement).where(Advertisement.id == req.advertisement_id))
        ).scalars().first()
        if not ad:
            self._raise_error(404, "ADVERTISEMENT_NOT_FOUND", "Advertisement not found.")
        await self._assert_ad_window_open(ad)

        duplicate = (
            await db.execute(
                select(Application.id).where(
                    and_(
                        Application.advertisement_id == req.advertisement_id,
                        Application.candidate_id == candidate.id,
                    )
                )
            )
        ).first()
        if duplicate:
            self._raise_error(409, "DUPLICATE_APPLICATION", "Candidate has already applied to this advertisement.")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                app_number = await self._next_application_number(db)
                application = Application(
                    advertisement_id=req.advertisement_id,
                    candidate_id=candidate.id,
                    institution_id=ad.institution_id,
                    course_id=ad.course_id,
                    academic_year=ad.academic_year,
                    application_number=app_number,
                    status=ApplicationStatus.DRAFT.value,
                    applied_designation=req.applied_designation,
                    cover_letter=req.cover_letter,
                    declaration_accepted=False,
                )
                db.add(application)
                await db.flush()
                
                await self._write_audit(
                    db,
                    "Application",
                    self._entity_id_from_uuid(application.id),
                    "CREATE_APPLICATION",
                    current_user.id,
                    new_value={"application_number": app_number, "status": ApplicationStatus.DRAFT.value},
                )
                await db.commit()
                return application
                
            except IntegrityError as exc:
                await db.rollback()
                if "application_number" in str(exc.orig).lower() and attempt < max_retries - 1:
                    continue # Retry with a new number
                raise # Re-raise if it's a different error or max retries reached

    async def upload_documents_bulk(
        self,
        db: AsyncSession,
        current_user: User,
        application_id: UUID,
        files: list[UploadFile],
        background_tasks: BackgroundTasks,
        document_type: str | None = None,
    ) -> list[ApplicationDocument]:
        candidate = await self._get_candidate_or_404(db, current_user.id)
        application = await self._get_application_for_candidate(db, application_id, candidate.id)
        if application.status != ApplicationStatus.DRAFT.value:
            self._raise_error(403, "APPLICATION_NOT_EDITABLE", "Documents can be uploaded only in DRAFT.")

        created_docs = []
        for file in files:
            if file.content_type not in ALLOWED_MIME_TYPES:
                continue # Skip invalid types for now or raise error

            payload = await file.read()
            await file.seek(0)
            size_kb = len(payload) // 1024
            if size_kb > MAX_FILE_SIZE_KB:
                continue

            # Use provided type or default to OTHER
            final_type = document_type or "OTHER"
            
            destination = f"{application.institution_id}/{application.id}/{final_type}_{uuid4().hex[:8]}"
            file_path = await save_file(file, destination)

            document = ApplicationDocument(
                application_id=application.id,
                candidate_id=candidate.id,
                document_type=final_type,
                file_name=file.filename or "document.bin",
                file_path=file_path,
                file_size_kb=size_kb,
                mime_type=file.content_type,
                is_required=False,
                validation_status="PENDING",
                uploaded_at=datetime.now(timezone.utc)
            )
            db.add(document)
            created_docs.append(document)

        await db.flush()
        for doc in created_docs:
            await self._write_audit(
                db,
                "ApplicationDocument",
                self._entity_id_from_uuid(doc.id),
                "UPLOAD_DOCUMENT",
                current_user.id,
                new_value={"document_type": doc.document_type, "application_id": str(application.id)},
            )
        await db.commit()
        return created_docs

    async def list_documents(
        self, db: AsyncSession, current_user: User, application_id: UUID
    ) -> list[ApplicationDocument]:
        application = (
            await db.execute(select(Application).where(Application.id == application_id))
        ).scalars().first()
        if not application:
            self._raise_error(404, "UNAUTHORIZED_ACCESS", "Application not found.")

        if current_user.role == RoleEnum.CANDIDATE:
            candidate = await self._get_candidate_or_404(db, current_user.id)
            if application.candidate_id != candidate.id:
                self._raise_error(403, "UNAUTHORIZED_ACCESS", "You do not have access to this application.")
        elif current_user.role == RoleEnum.PRINCIPAL:
            await verify_institution_access(application.institution_id, current_user)

        docs = (
            await db.execute(
                select(ApplicationDocument)
                .where(ApplicationDocument.application_id == application_id)
                .order_by(ApplicationDocument.uploaded_at.asc())
            )
        ).scalars().all()
        return docs

    async def submit_application(
        self, db: AsyncSession, current_user: User, application_id: UUID, req: ApplicationSubmitRequest
    ) -> dict[str, Any]:
        if not req.declaration_accepted:
            self._raise_error(400, "DECLARATION_NOT_ACCEPTED", "Declaration must be accepted before submission.")

        candidate = await self._get_candidate_or_404(db, current_user.id)
        if not candidate.is_profile_complete:
            self._raise_error(400, "PROFILE_INCOMPLETE", "Profile must be complete before submission.")

        application = await self._get_application_for_candidate(db, application_id, candidate.id)
        if application.status != ApplicationStatus.DRAFT.value:
            self._raise_error(400, "APPLICATION_NOT_EDITABLE", "Only DRAFT applications can be submitted.")

        ad = (
            await db.execute(select(Advertisement).where(Advertisement.id == application.advertisement_id))
        ).scalars().first()
        if not ad:
            self._raise_error(404, "ADVERTISEMENT_CLOSED", "Advertisement not found.")
        await self._assert_ad_window_open(ad)

        required_docs = (
            await db.execute(
                select(ApplicationDocument)
                .where(
                    and_(
                        ApplicationDocument.application_id == application.id,
                        ApplicationDocument.document_type.in_(REQUIRED_DOCUMENTS),
                    )
                )
            )
        ).scalars().all()

        present_types = {doc.document_type for doc in required_docs}
        missing = REQUIRED_DOCUMENTS - present_types
        if missing:
            self._raise_error(
                400,
                "REQUIRED_DOCUMENTS_MISSING",
                f"Required documents missing: {', '.join(sorted(missing))}",
            )

        # Relaxed for development: allow submission even if some documents have validation issues
        # invalid_required = [doc.document_type for doc in required_docs if doc.validation_status == "INVALID"]
        # if invalid_required:
        #     self._raise_error(
        #         400,
        #         "REQUIRED_DOCUMENTS_MISSING",
        #         f"Invalid required documents: {', '.join(sorted(set(invalid_required)))}",
        #     )

        application.declaration_accepted = True
        application.status = ApplicationStatus.SUBMITTED.value
        application.submitted_at = datetime.now(timezone.utc)

        await self._write_audit(
            db,
            "Application",
            self._entity_id_from_uuid(application.id),
            "SUBMIT_APPLICATION",
            current_user.id,
            new_value={"status": ApplicationStatus.SUBMITTED.value},
        )
        await db.commit()

        return {
            "application_number": application.application_number,
            "submitted_at": application.submitted_at,
            "status": application.status,
        }

    async def process_application_action(
        self, db: AsyncSession, current_user: User, application_id: UUID, req: ApplicationActionRequest
    ) -> Application:
        application = (
            await db.execute(select(Application).where(Application.id == application_id))
        ).scalars().first()
        if not application:
            self._raise_error(404, "APPLICATION_NOT_FOUND", "Application not found.")

        # Access check
        await self.assert_application_view_access(db, current_user, application)

        # Map action to actual status
        status_map = {
            ApplicationAction.APPROVE: ApplicationStatus.SHORTLISTED.value,
            ApplicationAction.REJECT: ApplicationStatus.REJECTED.value,
            ApplicationAction.UNDER_REVIEW: ApplicationStatus.UNDER_REVIEW.value,
        }
        
        old_status = application.status
        new_status = status_map[req.action]
        application.status = new_status
        application.reviewed_at = datetime.now(timezone.utc)
        
        # Sync with selection process if approved
        if req.action == ApplicationAction.APPROVE:
            # Check if already in shortlist
            sc_exists = (await db.execute(select(ShortlistedCandidate).where(
                and_(ShortlistedCandidate.application_id == application.id, ShortlistedCandidate.advertisement_id == application.advertisement_id)
            ))).scalars().first()
            
            if not sc_exists:
                db.add(ShortlistedCandidate(
                    advertisement_id=application.advertisement_id,
                    application_id=application.id,
                    candidate_id=application.candidate_id,
                    shortlisted_by=current_user.id,
                    shortlist_remarks=req.remarks or "Shortlisted via Application Review"
                ))
        
        if req.action == ApplicationAction.REJECT:
            application.rejection_reason = req.remarks
        
        await self._write_audit(
            db,
            "Application",
            self._entity_id_from_uuid(application.id),
            "PROCESS_ACTION",
            current_user.id,
            old_value={"status": old_status},
            new_value={"status": application.status, "remarks": req.remarks},
        )
        await db.commit()
        await db.refresh(application)
        return application

    async def withdraw_application(
        self, db: AsyncSession, current_user: User, application_id: UUID
    ) -> Application:
        candidate = await self._get_candidate_or_404(db, current_user.id)
        application = await self._get_application_for_candidate(db, application_id, candidate.id)

        if application.status not in {ApplicationStatus.DRAFT.value, ApplicationStatus.SUBMITTED.value}:
            self._raise_error(400, "APPLICATION_NOT_EDITABLE", "Only DRAFT/SUBMITTED applications can be withdrawn.")
        if application.status == ApplicationStatus.WITHDRAWN.value:
            self._raise_error(400, "APPLICATION_NOT_EDITABLE", "Application is already withdrawn.")

        application.status = ApplicationStatus.WITHDRAWN.value
        await self._write_audit(
            db,
            "Application",
            self._entity_id_from_uuid(application.id),
            "WITHDRAW_APPLICATION",
            current_user.id,
            new_value={"status": ApplicationStatus.WITHDRAWN.value},
        )
        await db.commit()
        return application

    async def list_my_applications(self, db: AsyncSession, current_user: User, skip: int = 0, limit: int = 10) -> tuple[list[dict[str, Any]], int]:
        candidate = await self._get_candidate_by_user(db, current_user.id)
        if not candidate:
            return [], 0

        stmt = (
            select(
                Application.id.label("application_id"),
                Application.application_number,
                Application.status,
                Application.academic_year,
                Application.advertisement_id,
                Institution.name.label("institution_name"),
                Course.name.label("course_name"),
            )
            .join(Institution, Institution.id == Application.institution_id)
            .join(Course, Course.id == Application.course_id)
            .where(Application.candidate_id == candidate.id)
        )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(Application.created_at.desc())
        if limit > 0:
            stmt = stmt.offset(skip).limit(limit)

        rows = (await db.execute(stmt)).mappings().all()

        result_list = [
            {
                "application_id": row["application_id"],
                "application_number": row["application_number"],
                "status": row["status"],
                "institution_name": row["institution_name"],
                "course_name": row["course_name"],
                "academic_year": row["academic_year"],
                "advertisement_id": str(row["advertisement_id"]),
                "advertisement_name": f"CHB Advertisement {row['academic_year']} - {row['course_name']}",
            }
            for row in rows
        ]
        return result_list, total

    async def list_applications(
        self,
        db: AsyncSession,
        current_user: User,
        advertisement_id: Optional[UUID] = None,
        status: Optional[str] = None,
        course_id: Optional[int] = None,
        academic_year: Optional[str] = None,
        skip: int = 0,
        limit: int = 10,
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = (
            select(
                Application.id.label("application_id"),
                Application.application_number,
                Application.status,
                Candidate.full_name.label("candidate_name"),
                Institution.name.label("institution_name"),
                Course.name.label("course_name"),
                Application.academic_year,
                Application.ai_confidence_score,
                Application.id.label("id"),
                func.sum(case((ApplicationDocument.validation_status == "INVALID", 1), else_=0)).label(
                    "invalid_documents"
                ),
                func.sum(case((ApplicationDocument.validation_status == "SUSPICIOUS", 1), else_=0)).label(
                    "suspicious_documents"
                ),
                func.sum(case((ApplicationDocument.validation_status == "PENDING", 1), else_=0)).label(
                    "pending_documents"
                ),
                func.sum(case((ApplicationDocument.validation_status == "VALID", 1), else_=0)).label(
                    "valid_documents"
                ),
            )
            .join(Candidate, Candidate.id == Application.candidate_id)
            .join(Institution, Institution.id == Application.institution_id)
            .join(Course, Course.id == Application.course_id)
            .outerjoin(ApplicationDocument, ApplicationDocument.application_id == Application.id)
            .group_by(
                Application.id,
                Application.application_number,
                Application.status,
                Candidate.full_name,
                Institution.name,
                Course.name,
                Application.academic_year,
                Application.ai_confidence_score,
                Application.created_at,
            )
        )

        if advertisement_id:
            stmt = stmt.where(Application.advertisement_id == advertisement_id)
        if status:
            if "," in status:
                stmt = stmt.where(Application.status.in_(status.split(",")))
            else:
                stmt = stmt.where(Application.status == status)
        if course_id:
            stmt = stmt.where(Application.course_id == course_id)
        if academic_year:
            stmt = stmt.where(Application.academic_year == academic_year)

        if current_user.role == RoleEnum.PRINCIPAL:
            if not current_user.institution_id:
                self._raise_error(403, "UNAUTHORIZED_ACCESS", "Principal institution scope is not configured.")
            stmt = stmt.where(Application.institution_id == current_user.institution_id)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(Application.created_at.desc())
        if limit > 0:
            stmt = stmt.offset(skip).limit(limit)

        rows = (await db.execute(stmt)).mappings().all()
        result_list = [
            {
                "application_id": row["application_id"],
                "application_number": row["application_number"],
                "status": row["status"],
                "candidate_name": row["candidate_name"],
                "institution_name": row["institution_name"],
                "course_name": row["course_name"],
                "academic_year": row["academic_year"],
                "ai_confidence_score": row["ai_confidence_score"],
                "id": row["id"],
                "invalid_documents": int(row["invalid_documents"] or 0),
                "suspicious_documents": int(row["suspicious_documents"] or 0),
                "pending_documents": int(row["pending_documents"] or 0),
                "valid_documents": int(row["valid_documents"] or 0),
            }
            for row in rows
        ]
        return result_list, total
