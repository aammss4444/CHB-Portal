from __future__ import annotations

import secrets
import string
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.dependencies.institution_scope import verify_institution_access
from app.models.appointment_acceptance import AppointmentAcceptance
from app.models.appointment_audit import AppointmentAudit, AppointmentAuditAction
from app.models.appointment_letter import AppointmentLetter, AppointmentLetterStatus
from app.models.appointment_template import AppointmentTemplate
from app.models.audit import AuditLog
from app.models.candidate import Candidate
from app.models.faculty_credentials import FacultyCredentials
from app.models.institution import Course, Institution
from app.models.selection_result import SelectionResult, SelectionResultStatus, FinalResultStatus

from app.models.user import RoleEnum, User
from app.modules.appointment.appointment_engine import AppointmentRenderError, generate_pdf, render_appointment_letter
from app.modules.appointment.schemas import (
    AppointmentApproveAction,
    AppointmentApproveRequest,
    AppointmentGenerateRequest,
    AppointmentRespondAction,
    AppointmentRespondRequest,
    AppointmentUpdateRequest,
)
from app.services.encryption_service import encrypt_bytes
from app.services.notification_service import (
    notify_letter_approved,
    notify_letter_issued,
    notify_letter_rejected,
    notify_waitlist_promotion,
    notify_waitlist_unavailable,
    send_credentials,
)
from app.services.storage_service import get_file_url, save_bytes_file


class AppointmentService:
    """Business logic for Step 6 appointment lifecycle and credential issuance."""

    @staticmethod
    def _raise_error(status_code: int, code: str, message: str) -> None:
        raise HTTPException(status_code=status_code, detail={"code": code, "message": message})

    @staticmethod
    def _entity_id_from_uuid(value: UUID) -> str:
        return str(value)

    @staticmethod
    def _status_value(letter: AppointmentLetter) -> str:
        return letter.status.value if hasattr(letter.status, "value") else str(letter.status)

    @staticmethod
    def _format_date(value: date) -> str:
        return value.strftime("%d %B %Y")

    @staticmethod
    def _format_currency(value: Decimal) -> str:
        return f"\u20b9{value:.2f}"

    async def _write_audit(
        self,
        db: AsyncSession,
        appointment_id: UUID,
        action: AppointmentAuditAction,
        user_id: int,
        remarks: Optional[str] = None,
        old_value: Optional[dict[str, Any]] = None,
        new_value: Optional[dict[str, Any]] = None,
    ) -> None:
        db.add(
            AppointmentAudit(
                appointment_letter_id=appointment_id,
                action=action.value,
                performed_by=user_id,
                remarks=remarks,
            )
        )
        db.add(
            AuditLog(
                entity_name="AppointmentLetter",
                entity_id=self._entity_id_from_uuid(appointment_id),
                action=action.value,
                user_id=user_id,
                old_value=old_value,
                new_value=new_value,
            )
        )

    async def _next_appointment_number(self, db: AsyncSession, year: int) -> str:
        prefix = f"CHB-APT-{year}-"
        count = (
            await db.execute(
                select(func.count(AppointmentLetter.id)).where(AppointmentLetter.appointment_number.like(f"{prefix}%"))
            )
        ).scalar_one()
        seq = int(count or 0) + 1
        return f"{prefix}{seq:05d}"

    async def _get_templates(self, db: AsyncSession) -> tuple[AppointmentTemplate, AppointmentTemplate]:
        # Use hardcoded templates explicitly as per requirements
        en_body = "Appointment Number: {{appointment_number}}\nDate: {{issue_date}}\n\nTo,\n{{candidate_name}}\n\nSubject: Appointment as {{designation}}\n\nYou are hereby appointed as {{designation}} at {{institution_name}}, {{course_name}} for academic year {{academic_year}}.\nYour joining date is {{joining_date}} and remuneration is {{salary_per_lecture}} per lecture.\n\nPlease report to the undersigned and complete formalities before joining.\n\nPrincipal\n{{principal_name}}\n"
        mr_body = "नियुक्ती क्रमांक: {{appointment_number}}\nदिनांक: {{issue_date}}\n\nप्रति,\n{{candidate_name}}\n\nविषय: {{designation}} म्हणून नियुक्ती\n\nआपली {{institution_name}}, {{course_name}} येथे शैक्षणिक वर्ष {{academic_year}} साठी {{designation}} म्हणून नियुक्ती करण्यात येत आहे.\nआपली रुजू होण्याची तारीख {{joining_date}} असून मानधन प्रति व्याख्यान {{salary_per_lecture}} असेल.\n\nकृपया निर्धारित तारखेपूर्वी आवश्यक कागदपत्रांसह हजर राहावे.\n\nप्राचार्य\n{{principal_name}}\n"
        
        tpl_en = AppointmentTemplate(language="EN", template_body=en_body, name="HARDCODED_EN")
        tpl_mr = AppointmentTemplate(language="MR", template_body=mr_body, name="HARDCODED_MR")
                
        return tpl_en, tpl_mr

    async def _get_letter_or_404(self, db: AsyncSession, appointment_id: UUID) -> AppointmentLetter:
        letter = (
            await db.execute(select(AppointmentLetter).where(AppointmentLetter.id == appointment_id))
        ).scalars().first()
        if not letter:
            self._raise_error(404, "NOT_FOUND", "Appointment letter not found")
        return letter

    async def _get_candidate_or_404(self, db: AsyncSession, candidate_id: UUID) -> Candidate:
        candidate = (
            await db.execute(select(Candidate).where(Candidate.id == candidate_id))
        ).scalars().first()
        if not candidate:
            self._raise_error(404, "NOT_FOUND", "Candidate not found")
        return candidate

    async def _get_audit_trail(self, db: AsyncSession, appointment_id: UUID) -> list[AppointmentAudit]:
        return (
            await db.execute(
                select(AppointmentAudit)
                .where(AppointmentAudit.appointment_letter_id == appointment_id)
                .order_by(AppointmentAudit.created_at.desc())
            )
        ).scalars().all()

    def _ensure_date_rules(self, joining_date: date, acceptance_deadline: date, require_future_joining: bool = True) -> None:
        pass

    async def _resolve_principal_for_institution(self, db: AsyncSession, institution_id: int) -> Optional[User]:
        return (
            await db.execute(
                select(User).where(
                    and_(User.role == RoleEnum.PRINCIPAL, User.institution_id == institution_id)
                )
            )
        ).scalars().first()

    async def _assert_institution_access(self, institution_id: int, current_user: User) -> None:
        try:
            await verify_institution_access(institution_id, current_user)
        except HTTPException as exc:
            if exc.status_code == 403:
                self._raise_error(
                    403, "UNAUTHORIZED_INSTITUTION", "You do not have access to this institution's data"
                )
            raise

    async def _notify_admins_and_principal_waitlist_unavailable(
        self,
        db: AsyncSession,
        institution_id: int,
        context: str,
    ) -> None:
        """Notify principal and all admins when waitlist promotion cannot proceed."""
        principal = await self._resolve_principal_for_institution(db, institution_id)
        if principal:
            await notify_waitlist_unavailable(principal, context)

        admins = (
            await db.execute(select(User).where(User.role == RoleEnum.ADMIN))
        ).scalars().all()
        for admin in admins:
            await notify_waitlist_unavailable(admin, context)

    async def _write_waitlist_audit(
        self,
        db: AsyncSession,
        declined_appointment_id: UUID,
        action: str,
        context: str,
        user_id: Optional[int],
    ) -> None:
        """Write waitlist promotion events to centralized audit logs."""
        if user_id is None:
            return
        db.add(
            AuditLog(
                entity_name="AppointmentLetter",
                entity_id=self._entity_id_from_uuid(declined_appointment_id),
                action=action,
                user_id=user_id,
                old_value=None,
                new_value={"context": context},
            )
        )

    async def generate_letter(self, db: AsyncSession, current_user: User, req: AppointmentGenerateRequest) -> AppointmentLetter:
        if current_user.role != RoleEnum.PRINCIPAL:
            self._raise_error(403, "HTTP_ERROR", "Only PRINCIPAL can generate appointment letters")

        self._ensure_date_rules(req.joining_date, req.acceptance_deadline, require_future_joining=True)

        selection_row = (
            await db.execute(
                select(
                    SelectionResult,
                    SelectionResult.advertisement_id,
                    Institution.name.label("institution_name"),
                    Course.name.label("course_name"),
                )
                .join(Institution, Institution.id == SelectionResult.institution_id)
                .join(Course, Course.id == SelectionResult.course_id)
                .where(SelectionResult.id == req.selection_result_id)
            )
        ).first()
        if not selection_row:
            self._raise_error(404, "NOT_FOUND", "Selection result not found")

        selection_result, advertisement_id, institution_name, course_name = selection_row
        await self._assert_institution_access(selection_result.institution_id, current_user)

        if (
            selection_result.status != FinalResultStatus.CONFIRMED.value
            or selection_result.result_status != SelectionResultStatus.SELECTED.value
        ):
            self._raise_error(
                400,
                "SELECTION_NOT_CONFIRMED",
                "Selection result must be CONFIRMED and SELECTED to generate an appointment letter",
            )

        duplicate = (
            await db.execute(
                select(AppointmentLetter.id).where(AppointmentLetter.selection_result_id == req.selection_result_id)
            )
        ).scalar_one_or_none()
        if duplicate:
            self._raise_error(409, "LETTER_ALREADY_EXISTS", "Appointment letter already exists for this selection result")

        candidate = await self._get_candidate_or_404(db, selection_result.candidate_id)
        tpl_en, tpl_mr = await self._get_templates(db)

        year_now = datetime.utcnow().year
        appointment_number = await self._next_appointment_number(db, year_now)
        context = {
            "candidate_name": candidate.full_name,
            "designation": "Assistant Professor",
            "institution_name": institution_name,
            "course_name": course_name,
            "academic_year": selection_result.academic_year,
            "joining_date": self._format_date(req.joining_date),
            "salary_per_lecture": self._format_currency(req.salary_per_lecture),
            "appointment_number": appointment_number,
            "principal_name": current_user.full_name or "Principal",
            "issue_date": self._format_date(date.today()),
            "acceptance_deadline": self._format_date(req.acceptance_deadline),
        }
        try:
            content_en = render_appointment_letter(tpl_en.template_body, context)
            content_mr = render_appointment_letter(tpl_mr.template_body, context)
        except AppointmentRenderError as exc:
            self._raise_error(400, "TEMPLATE_NOT_FOUND", str(exc))

        letter = AppointmentLetter(
            appointment_number=appointment_number,
            selection_result_id=selection_result.id,
            candidate_id=selection_result.candidate_id,
            institution_id=selection_result.institution_id,
            course_id=selection_result.course_id,
            academic_year=selection_result.academic_year,
            designation="Assistant Professor",
            joining_date=req.joining_date,
            salary_per_lecture=req.salary_per_lecture,
            content_en=content_en,
            content_mr=content_mr,
            status=AppointmentLetterStatus.DRAFT.value,
            acceptance_deadline=req.acceptance_deadline,
            created_by=current_user.id,
        )
        db.add(letter)
        await db.flush()
        await self._write_audit(
            db,
            letter.id,
            AppointmentAuditAction.GENERATED,
            current_user.id,
            new_value={"status": AppointmentLetterStatus.DRAFT.value, "advertisement_id": str(advertisement_id)},
        )
        await db.commit()
        return letter

    async def get_letter(self, db: AsyncSession, current_user: User, appointment_id: UUID) -> dict[str, Any]:
        letter = await self._get_letter_or_404(db, appointment_id)

        if current_user.role == RoleEnum.PRINCIPAL:
            await self._assert_institution_access(letter.institution_id, current_user)
        elif current_user.role == RoleEnum.CANDIDATE:
            candidate = (
                await db.execute(select(Candidate).where(Candidate.user_id == current_user.id))
            ).scalars().first()
            if not candidate or candidate.id != letter.candidate_id:
                self._raise_error(403, "UNAUTHORIZED_INSTITUTION", "You do not have access to this appointment letter")
        elif current_user.role != RoleEnum.ADMIN:
            self._raise_error(403, "HTTP_ERROR", "Operation not permitted for this role")

        audits = await self._get_audit_trail(db, letter.id)
        audit_payload = [
            {
                "action": row.action,
                "performed_by": row.performed_by,
                "remarks": row.remarks,
                "created_at": row.created_at,
            }
            for row in audits
        ]
        payload = {
            "id": letter.id,
            "appointment_number": letter.appointment_number,
            "selection_result_id": letter.selection_result_id,
            "candidate_id": letter.candidate_id,
            "institution_id": letter.institution_id,
            "course_id": letter.course_id,
            "academic_year": letter.academic_year,
            "designation": letter.designation,
            "joining_date": letter.joining_date,
            "salary_per_lecture": letter.salary_per_lecture,
            "content_en": letter.content_en,
            "content_mr": letter.content_mr,
            "status": letter.status,
            "rejection_reason": letter.rejection_reason,
            "generated_at": letter.generated_at,
            "approved_by": letter.approved_by,
            "approved_at": letter.approved_at,
            "issued_at": letter.issued_at,
            "issued_by": letter.issued_by,
            "acceptance_deadline": letter.acceptance_deadline,
            "created_by": letter.created_by,
            "created_at": letter.created_at,
            "updated_at": letter.updated_at,
            "audit_trail": audit_payload,
        }

        if current_user.role == RoleEnum.CANDIDATE:
            payload["download_url"] = await get_file_url(letter.file_path) if letter.file_path else None
            payload["file_path"] = None
            
            # If accepted, show credentials
            if letter.status == AppointmentLetterStatus.ACCEPTED.value:
                creds = (
                    await db.execute(
                        select(FacultyCredentials).where(FacultyCredentials.appointment_letter_id == letter.id)
                    )
                ).scalars().first()
                if creds:
                    payload["credentials"] = {
                        "username": creds.portal_username,
                        "password": creds.temp_password_plain,
                        "faculty_code": creds.faculty_code,
                        "issued_at": creds.credential_issued_at
                    }
        else:
            payload["file_path"] = letter.file_path
            payload["download_url"] = await get_file_url(letter.file_path) if letter.file_path else None
            
            # Principal can also see if credentials were issued (but maybe not the password)
            creds = (
                await db.execute(
                    select(FacultyCredentials).where(FacultyCredentials.appointment_letter_id == letter.id)
                )
            ).scalars().first()
            if creds:
                payload["credentials"] = {
                    "username": creds.portal_username,
                    "faculty_code": creds.faculty_code,
                    "issued_at": creds.credential_issued_at,
                    "is_active": creds.is_active
                }

        return payload

    async def update_letter(
        self, db: AsyncSession, current_user: User, appointment_id: UUID, req: AppointmentUpdateRequest
    ) -> AppointmentLetter:
        letter = await self._get_letter_or_404(db, appointment_id)
        await self._assert_institution_access(letter.institution_id, current_user)

        if self._status_value(letter) not in {AppointmentLetterStatus.DRAFT.value, AppointmentLetterStatus.REJECTED.value}:
            self._raise_error(403, "LETTER_IMMUTABLE", "Only DRAFT or REJECTED letters can be edited")

        old_values = {
            "joining_date": str(letter.joining_date),
            "salary_per_lecture": str(letter.salary_per_lecture),
            "acceptance_deadline": str(letter.acceptance_deadline) if letter.acceptance_deadline else None,
            "content_en": letter.content_en,
            "content_mr": letter.content_mr,
        }

        if req.joining_date is not None:
            letter.joining_date = req.joining_date
        if req.salary_per_lecture is not None:
            letter.salary_per_lecture = req.salary_per_lecture
        if req.acceptance_deadline is not None:
            letter.acceptance_deadline = req.acceptance_deadline
        content_changed = False
        if req.content_en is not None:
            letter.content_en = req.content_en
            content_changed = True
        if req.content_mr is not None:
            letter.content_mr = req.content_mr
            content_changed = True

        self._ensure_date_rules(letter.joining_date, letter.acceptance_deadline, require_future_joining=True)
        if content_changed:
            letter.file_path = None

        await self._write_audit(
            db,
            letter.id,
            AppointmentAuditAction.EDITED,
            current_user.id,
            old_value=old_values,
            new_value={
                "joining_date": str(letter.joining_date),
                "salary_per_lecture": str(letter.salary_per_lecture),
                "acceptance_deadline": str(letter.acceptance_deadline) if letter.acceptance_deadline else None,
                "content_en": letter.content_en,
                "content_mr": letter.content_mr,
            },
        )
        await db.commit()
        return letter

    async def submit_letter_directly(self, db: AsyncSession, current_user: User, appointment_id: UUID) -> AppointmentLetter:
        letter = await self._get_letter_or_404(db, appointment_id)
        await self._assert_institution_access(letter.institution_id, current_user)

        if self._status_value(letter) not in {AppointmentLetterStatus.DRAFT.value, AppointmentLetterStatus.REJECTED.value}:
            self._raise_error(400, "INVALID_STATUS_TRANSITION", "Only DRAFT or REJECTED letters can be submitted")

        if not letter.content_en.strip() or not letter.content_mr.strip():
            self._raise_error(400, "INVALID_STATUS_TRANSITION", "content_en and content_mr must not be empty")
        self._ensure_date_rules(letter.joining_date, letter.acceptance_deadline, require_future_joining=False)

        # Generate PDF and finalize
        pdf_bytes = generate_pdf(letter.content_en, letter.appointment_number)
        encrypted_pdf = encrypt_bytes(pdf_bytes)
        file_path = f"appointments/{letter.institution_id}/{letter.academic_year}/{letter.appointment_number}.pdf"
        stored_path = await save_bytes_file(encrypted_pdf, file_path)

        letter.file_path = stored_path
        letter.status = AppointmentLetterStatus.ISSUED.value
        letter.issued_by = current_user.id
        letter.issued_at = datetime.utcnow()
        
        await self._write_audit(
            db, 
            letter.id, 
            AppointmentAuditAction.SUBMITTED, 
            current_user.id, 
            new_value={"status": letter.status, "file_path": letter.file_path}
        )
        
        # Notify candidate immediately
        candidate = await self._get_candidate_or_404(db, letter.candidate_id)
        await notify_letter_issued(candidate, letter)
        
        await db.commit()
        return letter

    async def approve_letter(
        self, db: AsyncSession, current_user: User, appointment_id: UUID, req: AppointmentApproveRequest
    ) -> AppointmentLetter:
        letter = await self._get_letter_or_404(db, appointment_id)
        if self._status_value(letter) != AppointmentLetterStatus.PENDING_APPROVAL.value:
            self._raise_error(400, "INVALID_STATUS_TRANSITION", "Only PENDING_APPROVAL letters can be approved/rejected")

        principal = await self._resolve_principal_for_institution(db, letter.institution_id)

        if req.action == AppointmentApproveAction.APPROVE:
            pdf_bytes = generate_pdf(letter.content_en, letter.appointment_number)
            encrypted_pdf = encrypt_bytes(pdf_bytes)
            file_path = f"appointments/{letter.institution_id}/{letter.academic_year}/{letter.appointment_number}.pdf"
            stored_path = await save_bytes_file(encrypted_pdf, file_path)

            letter.file_path = stored_path
            letter.status = AppointmentLetterStatus.APPROVED.value
            letter.approved_by = current_user.id
            letter.approved_at = datetime.utcnow()
            letter.rejection_reason = None
            await self._write_audit(
                db,
                letter.id,
                AppointmentAuditAction.APPROVED,
                current_user.id,
                new_value={"status": letter.status, "file_path": letter.file_path},
            )
            if principal:
                await notify_letter_approved(principal, letter)
        else:
            if not req.remarks or not req.remarks.strip():
                self._raise_error(400, "INVALID_STATUS_TRANSITION", "remarks are required when action is REJECT")
            letter.status = AppointmentLetterStatus.REJECTED.value
            letter.rejection_reason = req.remarks.strip()
            await self._write_audit(
                db,
                letter.id,
                AppointmentAuditAction.REJECTED,
                current_user.id,
                remarks=letter.rejection_reason,
                new_value={"status": letter.status, "rejection_reason": letter.rejection_reason},
            )
            if principal:
                await notify_letter_rejected(principal, letter, letter.rejection_reason)

        await db.commit()
        return letter

    async def issue_letter(self, db: AsyncSession, current_user: User, appointment_id: UUID) -> AppointmentLetter:
        letter = await self._get_letter_or_404(db, appointment_id)
        if self._status_value(letter) != AppointmentLetterStatus.APPROVED.value:
            self._raise_error(400, "INVALID_STATUS_TRANSITION", "Only APPROVED letters can be issued")

        letter.status = AppointmentLetterStatus.ISSUED.value
        letter.issued_by = current_user.id
        letter.issued_at = datetime.utcnow()
        await self._write_audit(
            db,
            letter.id,
            AppointmentAuditAction.ISSUED,
            current_user.id,
            new_value={
                "status": letter.status,
                "issued_at": letter.issued_at.isoformat(),
                "acceptance_deadline": str(letter.acceptance_deadline),
            },
        )

        candidate = await self._get_candidate_or_404(db, letter.candidate_id)
        await notify_letter_issued(candidate, letter)
        await db.commit()
        return letter

    async def respond_letter(
        self,
        db: AsyncSession,
        current_user: User,
        appointment_id: UUID,
        req: AppointmentRespondRequest,
        ip_address: Optional[str],
    ) -> AppointmentLetter:
        letter = await self._get_letter_or_404(db, appointment_id)
        if self._status_value(letter) != AppointmentLetterStatus.ISSUED.value:
            self._raise_error(400, "INVALID_STATUS_TRANSITION", "Only ISSUED letters can be responded to")

        candidate = (
            await db.execute(select(Candidate).where(Candidate.user_id == current_user.id))
        ).scalars().first()
        if not candidate or candidate.id != letter.candidate_id:
            self._raise_error(403, "UNAUTHORIZED_INSTITUTION", "You can respond only to your own appointment letter")

        if letter.acceptance_deadline and date.today() > letter.acceptance_deadline:
            self._raise_error(400, "ACCEPTANCE_DEADLINE_PASSED", "Acceptance deadline has passed")

        existing_response = (
            await db.execute(
                select(AppointmentAcceptance.id).where(AppointmentAcceptance.appointment_letter_id == letter.id)
            )
        ).scalar_one_or_none()
        if existing_response:
            self._raise_error(403, "ALREADY_RESPONDED", "Candidate has already responded to this appointment letter")

        db.add(
            AppointmentAcceptance(
                appointment_letter_id=letter.id,
                candidate_id=candidate.id,
                action=req.action.value,
                remarks=req.remarks,
                ip_address=ip_address,
            )
        )

        if req.action == AppointmentRespondAction.ACCEPTED:
            letter.status = AppointmentLetterStatus.ACCEPTED.value
            await self.issue_credentials(letter.id, letter.candidate_id, letter.institution_id, db)
            await self._write_audit(
                db, letter.id, AppointmentAuditAction.ACCEPTED, current_user.id, remarks=req.remarks
            )
            await self._write_audit(
                db, letter.id, AppointmentAuditAction.CREDENTIALS_ISSUED, current_user.id
            )
        else:
            letter.status = AppointmentLetterStatus.DECLINED.value
            await self.promote_from_waitlist(letter.id, db)
            await self._write_audit(
                db, letter.id, AppointmentAuditAction.DECLINED, current_user.id, remarks=req.remarks
            )

        await db.commit()
        return letter

    async def cancel_letter(
        self, db: AsyncSession, current_user: User, appointment_id: UUID, remarks: str
    ) -> AppointmentLetter:
        letter = await self._get_letter_or_404(db, appointment_id)
        status = self._status_value(letter)
        if status == AppointmentLetterStatus.ACCEPTED.value:
            self._raise_error(403, "CANNOT_CANCEL_ACCEPTED_LETTER", "Accepted appointment letter cannot be cancelled")
        if status not in {
            AppointmentLetterStatus.DRAFT.value,
            AppointmentLetterStatus.PENDING_APPROVAL.value,
            AppointmentLetterStatus.APPROVED.value,
            AppointmentLetterStatus.ISSUED.value,
        }:
            self._raise_error(400, "INVALID_STATUS_TRANSITION", "Appointment letter cannot be cancelled in current status")

        letter.status = AppointmentLetterStatus.CANCELLED.value
        creds = (
            await db.execute(
                select(FacultyCredentials).where(FacultyCredentials.appointment_letter_id == letter.id)
            )
        ).scalars().first()
        if creds:
            creds.is_active = False

        await self._write_audit(
            db,
            letter.id,
            AppointmentAuditAction.CANCELLED,
            current_user.id,
            remarks=remarks,
            new_value={"status": letter.status},
        )
        await db.commit()
        return letter

    async def delete_letter(self, db: AsyncSession, current_user: User, appointment_id: UUID) -> None:
        if current_user.role != RoleEnum.PRINCIPAL:
            self._raise_error(403, "HTTP_ERROR", "Only PRINCIPAL can delete appointment letters")

        letter = await self._get_letter_or_404(db, appointment_id)
        await self._assert_institution_access(letter.institution_id, current_user)

        # Delete audits first to avoid FK constraint violation
        await db.execute(
            AppointmentAudit.__table__.delete().where(AppointmentAudit.appointment_letter_id == letter.id)
        )
        
        await db.delete(letter)
        
        db.add(
            AuditLog(
                entity_name="AppointmentLetter",
                entity_id=self._entity_id_from_uuid(letter.id),
                action="DELETED",
                user_id=current_user.id,
                old_value={"appointment_number": letter.appointment_number, "status": letter.status},
            )
        )
        await db.commit()

    async def trigger_credentials(self, db: AsyncSession, current_user: User, appointment_id: UUID) -> FacultyCredentials:
        letter = await self._get_letter_or_404(db, appointment_id)
        if self._status_value(letter) != AppointmentLetterStatus.ACCEPTED.value:
            self._raise_error(400, "INVALID_STATUS_TRANSITION", "Credentials can be issued only for ACCEPTED letters")
        creds = (
            await db.execute(
                select(FacultyCredentials).where(FacultyCredentials.appointment_letter_id == letter.id)
            )
        ).scalars().first()
        if creds and creds.is_active:
            self._raise_error(409, "CREDENTIALS_ALREADY_ISSUED", "Active credentials already exist for this letter")

        credential = await self.issue_credentials(letter.id, letter.candidate_id, letter.institution_id, db)
        await self._write_audit(
            db, letter.id, AppointmentAuditAction.CREDENTIALS_ISSUED, current_user.id
        )
        await db.commit()
        return credential

    async def list_institution_letters(
        self,
        db: AsyncSession,
        current_user: User,
        institution_id: int,
        academic_year: Optional[str],
        status: Optional[str],
        course_id: Optional[int],
        page: int,
        size: int,
    ) -> dict[str, Any]:
        if current_user.role == RoleEnum.PRINCIPAL:
            await self._assert_institution_access(institution_id, current_user)

        filters = [AppointmentLetter.institution_id == institution_id]
        if academic_year:
            filters.append(AppointmentLetter.academic_year == academic_year)
        if status:
            filters.append(AppointmentLetter.status == status)
        if course_id:
            filters.append(AppointmentLetter.course_id == course_id)

        total = (
            await db.execute(select(func.count(AppointmentLetter.id)).where(and_(*filters)))
        ).scalar_one()

        rows = (
            await db.execute(
                select(
                    AppointmentLetter.id,
                    AppointmentLetter.appointment_number,
                    Candidate.full_name.label("candidate_name"),
                    AppointmentLetter.status,
                    Course.name.label("Course"),
                    AppointmentLetter.joining_date,
                    AppointmentLetter.candidate_id,
                    FacultyCredentials.id.label("credential_id"),
                )
                .join(Candidate, Candidate.id == AppointmentLetter.candidate_id)
                .join(Course, Course.id == AppointmentLetter.course_id)
                .outerjoin(
                    FacultyCredentials, FacultyCredentials.appointment_letter_id == AppointmentLetter.id
                )
                .where(and_(*filters))
                .order_by(AppointmentLetter.created_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        ).mappings().all()

        items = [
            {
                "id": row["id"],
                "appointment_number": row["appointment_number"],
                "candidate_name": row["candidate_name"],
                "status": row["status"],
                "course": row["Course"],
                "joining_date": row["joining_date"],
                "candidate_id": str(row["candidate_id"]),
                "credentials_issued": bool(row["credential_id"]),
                "faculty_credential_id": row["credential_id"],
            }
            for row in rows
        ]
        return {"total": int(total or 0), "page": page, "size": size, "items": items}

    async def list_candidate_letters(self, db: AsyncSession, current_user: User) -> list[dict[str, Any]]:
        candidate = (
            await db.execute(select(Candidate).where(Candidate.user_id == current_user.id))
        ).scalars().first()
        if not candidate:
            return []

        rows = (
            await db.execute(
                select(
                    AppointmentLetter.id,
                    AppointmentLetter.appointment_number,
                    Institution.name.label("institution_name"),
                    AppointmentLetter.status,
                    Course.name.label("course_name"),
                    AppointmentLetter.joining_date,
                    AppointmentLetter.issued_at,
                )
                .join(Institution, Institution.id == AppointmentLetter.institution_id)
                .join(Course, Course.id == AppointmentLetter.course_id)
                .where(and_(
                    AppointmentLetter.candidate_id == candidate.id,
                    AppointmentLetter.status != AppointmentLetterStatus.DRAFT.value
                ))
                .order_by(AppointmentLetter.issued_at.desc())
            )
        ).mappings().all()

        return [dict(row) for row in rows]

    async def issue_credentials(
        self, appointment_letter_id: UUID, candidate_id: UUID, institution_id: int, db: AsyncSession
    ) -> FacultyCredentials:
        """Issue faculty credentials for an accepted appointment letter."""
        existing = (
            await db.execute(
                select(FacultyCredentials).where(FacultyCredentials.appointment_letter_id == appointment_letter_id)
            )
        ).scalars().first()
        if existing:
            if existing.is_active:
                self._raise_error(409, "CREDENTIALS_ALREADY_ISSUED", "Credentials are already issued")
            existing.is_active = True
            return existing

        candidate = await self._get_candidate_or_404(db, candidate_id)
        institution = (
            await db.execute(select(Institution).where(Institution.id == institution_id))
        ).scalars().first()
        if not institution:
            self._raise_error(404, "NOT_FOUND", "Institution not found")

        current_year = datetime.utcnow().year
        inst_code = institution.code.upper()
        seq = (
            await db.execute(
                select(func.count(FacultyCredentials.id)).where(FacultyCredentials.institution_id == institution_id)
            )
        ).scalar_one()
        faculty_code = f"FAC-{inst_code}-{current_year}-{int(seq or 0) + 1:04d}"

        name_parts = (candidate.full_name or "faculty member").strip().split()
        firstname = name_parts[0].lower() if name_parts else "faculty"
        lastname = name_parts[-1].lower() if len(name_parts) > 1 else "member"
        domain = f"{institution.code.lower()}.chb"
        base_local = f"{firstname}.{lastname}"
        username_local = base_local
        counter = 0
        while True:
            portal_username = f"{username_local}@{domain}"
            conflict = (
                await db.execute(
                    select(User.id).where(User.email == portal_username)
                )
            ).scalar_one_or_none()
            if not conflict:
                break
            counter += 1
            username_local = f"{base_local}{counter:02d}"

        temp_password = self._generate_temp_password(8)
        temp_password_hash = get_password_hash(temp_password)

        faculty_user = User(
            email=portal_username,
            hashed_password=temp_password_hash,
            role=RoleEnum.FACULTY,
            full_name=candidate.full_name,
            phone_number=candidate.mobile,
            institution_id=institution_id,
            is_active=True,
            force_password_change=True,
        )
        db.add(faculty_user)
        await db.flush()

        creds = FacultyCredentials(
            appointment_letter_id=appointment_letter_id,
            candidate_id=candidate_id,
            institution_id=institution_id,
            user_id=faculty_user.id,
            faculty_code=faculty_code,
            portal_username=portal_username,
            temp_password_hash=temp_password_hash,
            temp_password_plain=temp_password,
            credential_issued_at=datetime.utcnow(),
            is_active=True,
        )
        db.add(creds)
        await db.flush()

        await send_credentials(candidate, portal_username, temp_password)
        return creds

    async def promote_from_waitlist(self, declined_appointment_id: UUID, db: AsyncSession) -> Optional[AppointmentLetter]:
        """Promote next waitlisted candidate and generate a new DRAFT letter."""
        declined = await self._get_letter_or_404(db, declined_appointment_id)
        actor_id = declined.created_by
        if not actor_id:
            first_admin = (await db.execute(select(User).where(User.role == RoleEnum.ADMIN))).scalars().first()
            if first_admin:
                actor_id = first_admin.id
        if not actor_id:
            first_user = (await db.execute(select(User).order_by(User.id.asc()))).scalars().first()
            if first_user:
                actor_id = first_user.id
        base_row = (
            await db.execute(
                select(SelectionResult, SelectionResult.advertisement_id)
                .where(SelectionResult.id == declined.selection_result_id)
            )
        ).first()
        if not base_row:
            await self._write_waitlist_audit(
                db,
                declined_appointment_id,
                "WAITLIST_PROMOTION_SKIPPED",
                "Selection result base row not found",
                actor_id,
            )
            return None
        _, advertisement_id = base_row

        waitlist_rows = (
            await db.execute(
                select(SelectionResult)
                .join(SelectionRound, SelectionRound.id == SelectionResult.round_id)
                .where(
                    and_(
                        SelectionRound.advertisement_id == advertisement_id,
                        SelectionResult.result_status == SelectionResultStatus.WAITLISTED.value,
                        SelectionResult.status == FinalResultStatus.CONFIRMED.value,
                    )
                )
                .order_by(SelectionResult.waitlist_position.asc())
            )
        ).scalars().all()
        if not waitlist_rows:
            context = (
                f"No waitlisted candidate available for advertisement={advertisement_id} "
                f"institution={declined.institution_id}"
            )
            print(f"[WAITLIST] {context}")
            await self._write_waitlist_audit(db, declined_appointment_id, "WAITLIST_PROMOTION_SKIPPED", context, actor_id)
            await self._notify_admins_and_principal_waitlist_unavailable(db, declined.institution_id, context)
            return None

        waitlist_row = None
        for candidate_result in waitlist_rows:
            exists = (
                await db.execute(
                    select(AppointmentLetter.id).where(AppointmentLetter.selection_result_id == candidate_result.id)
                )
            ).scalar_one_or_none()
            if not exists:
                waitlist_row = candidate_result
                break

        if not waitlist_row:
            context = (
                f"No eligible waitlisted candidate for advertisement={advertisement_id} "
                f"institution={declined.institution_id}"
            )
            print(f"[WAITLIST] {context}")
            await self._write_waitlist_audit(db, declined_appointment_id, "WAITLIST_PROMOTION_SKIPPED", context, actor_id)
            await self._notify_admins_and_principal_waitlist_unavailable(db, declined.institution_id, context)
            return None

        principal = await self._resolve_principal_for_institution(db, waitlist_row.institution_id)
        if not principal:
            context = (
                f"Principal not configured for institution={waitlist_row.institution_id}; "
                "waitlist promotion skipped"
            )
            print(f"[WAITLIST] {context}")
            await self._write_waitlist_audit(db, declined_appointment_id, "WAITLIST_PROMOTION_SKIPPED", context, actor_id)
            await self._notify_admins_and_principal_waitlist_unavailable(db, waitlist_row.institution_id, context)
            return None

        req = AppointmentGenerateRequest(
            selection_result_id=waitlist_row.id,
            joining_date=max(date.today() + timedelta(days=15), declined.joining_date),
            salary_per_lecture=declined.salary_per_lecture,
            acceptance_deadline=max(date.today() + timedelta(days=7), declined.joining_date - timedelta(days=3)),
        )
        letter = await self.generate_letter(db, principal, req)
        candidate = await self._get_candidate_or_404(db, waitlist_row.candidate_id)
        await notify_waitlist_promotion(candidate, letter)
        await self._write_waitlist_audit(
            db,
            declined_appointment_id,
            "WAITLIST_PROMOTED",
            f"Promoted selection_result_id={waitlist_row.id} to appointment_id={letter.id}",
            actor_id,
        )
        return letter

    @staticmethod
    def _generate_temp_password(length: int = 8) -> str:
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        while True:
            pwd = "".join(secrets.choice(alphabet) for _ in range(length))
            if (
                any(c.islower() for c in pwd)
                and any(c.isupper() for c in pwd)
                and any(c.isdigit() for c in pwd)
                and any(c in "!@#$%^&*" for c in pwd)
            ):
                return pwd
