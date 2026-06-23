from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, extract, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.dependencies.institution_scope import verify_institution_access
from app.models.academic_calendar import AcademicCalendar, CalendarDayType
from app.models.appointment_letter import AppointmentLetter, AppointmentLetterStatus
from app.models.attendance_anomaly import AnomalySeverity, AttendanceAnomaly
from app.models.audit import AuditLog
from app.models.daily_attendance_summary import DailyAttendanceSummary
from app.models.faculty_credentials import FacultyCredentials
from app.models.institution import Course
from app.models.lecture_log import LectureLog, LectureLogStatus, LectureLogType
from app.models.lecture_log_audit import LectureLogAudit, LectureLogAuditAction
from app.models.timetable_slot import TimetableLectureType, TimetableSlot
from app.models.user import RoleEnum, User
from app.modules.attendance.attendance_anomaly_engine import run_attendance_anomaly_check
from app.modules.attendance.schemas import (
    AnomalyResponse,
    CalendarEntry,
    CalendarEntryRequest,
    CalendarEntryResponse,
    DailyAttendanceSummaryResponse,
    LectureLogCreateRequest,
    LectureLogInput,
    LectureLogResponse,
    LectureLogUpdateRequest,
    TimetableSlotCreateRequest,
    TimetableSlotInput,
    TimetableSlotResponse,
    TimetableSlotUpdateRequest,
)


class AttendanceService:
    """Attendance and work-log business logic for Step 7."""

    @staticmethod
    def _raise_error(status_code: int, code: str, message: str) -> None:
        raise HTTPException(status_code=status_code, detail={"code": code, "message": message})

    @staticmethod
    def _entity_id_from_uuid(value: UUID) -> str:
        return str(value)

    @staticmethod
    def _day_name(value: date) -> str:
        return value.strftime("%A").upper()

    @staticmethod
    def _enum_value(value: Any) -> str:
        return value.value if hasattr(value, "value") else str(value)

    async def _write_audit_log(
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

    async def _write_lecture_log_audit(
        self,
        db: AsyncSession,
        lecture_log_id: UUID,
        action: LectureLogAuditAction,
        performed_by: int,
        remarks: Optional[str] = None,
    ) -> None:
        db.add(
            LectureLogAudit(
                lecture_log_id=lecture_log_id,
                action=action.value,
                performed_by=performed_by,
                remarks=remarks,
            )
        )

    async def _get_faculty_context(
        self, db: AsyncSession, current_user: User
    ) -> tuple[FacultyCredentials, AppointmentLetter]:
        """Resolve the logged-in faculty user's credential and accepted appointment."""
        row = (
            await db.execute(
                select(FacultyCredentials, AppointmentLetter)
                .join(AppointmentLetter, AppointmentLetter.id == FacultyCredentials.appointment_letter_id)
                .where(FacultyCredentials.user_id == current_user.id)
            )
        ).first()
        if not row:
            self._raise_error(403, "UNAUTHORIZED_ACCESS", "Faculty access is restricted to own records")
        return row

    async def _get_accepted_appointment(self, db: AsyncSession, credential: FacultyCredentials) -> AppointmentLetter:
        """Load the accepted appointment attached to the faculty credential."""
        appointment = (
            await db.execute(
                select(AppointmentLetter).where(
                    AppointmentLetter.id == credential.appointment_letter_id,
                    AppointmentLetter.status == AppointmentLetterStatus.ACCEPTED.value,
                )
            )
        ).scalars().first()
        if not appointment:
            self._raise_error(400, "HTTP_ERROR", "Accepted appointment is required for attendance operations")
        return appointment

    async def _get_credential_or_404(self, db: AsyncSession, credential_id: UUID) -> FacultyCredentials:
        credential = (
            await db.execute(select(FacultyCredentials).where(FacultyCredentials.id == credential_id))
        ).scalars().first()
        if not credential:
            self._raise_error(404, "NOT_FOUND", "Faculty credential not found")
        return credential

    async def _get_log_or_404(self, db: AsyncSession, log_id: UUID) -> LectureLog:
        log = (await db.execute(select(LectureLog).where(LectureLog.id == log_id))).scalars().first()
        if not log:
            self._raise_error(404, "NOT_FOUND", "Lecture log not found")
        return log

    async def _get_summary(
        self, db: AsyncSession, faculty_credential_id: UUID, attendance_date: date
    ) -> Optional[DailyAttendanceSummary]:
        return (
            await db.execute(
                select(DailyAttendanceSummary).where(
                    DailyAttendanceSummary.faculty_credential_id == faculty_credential_id,
                    DailyAttendanceSummary.attendance_date == attendance_date,
                )
            )
        ).scalars().first()

    async def _ensure_principal_scope(self, current_user: User, institution_id: int) -> None:
        """Enforce principal institution scoping."""
        try:
            await verify_institution_access(institution_id, current_user)
        except HTTPException:
            self._raise_error(403, "UNAUTHORIZED_ACCESS", "You do not have access to this institution's data")

    async def _ensure_credential_active(self, credential: FacultyCredentials) -> None:
        """Ensure Step 7 gate is open for the faculty credential."""
        if not credential.is_active:
            self._raise_error(
                403,
                "FACULTY_CREDENTIALS_INACTIVE",
                "Faculty credentials must be active before attendance can be recorded",
            )

    async def _get_calendar_entry(
        self, db: AsyncSession, institution_id: int, academic_year: str, attendance_date: date
    ) -> Optional[AcademicCalendar]:
        return (
            await db.execute(
                select(AcademicCalendar).where(
                    AcademicCalendar.institution_id == institution_id,
                    AcademicCalendar.academic_year == academic_year,
                    AcademicCalendar.calendar_date == attendance_date,
                )
            )
        ).scalars().first()

    async def _get_slot_match(
        self,
        db: AsyncSession,
        faculty_credential_id: UUID,
        academic_year: str,
        lecture_date: date,
        slot_number: int,
    ) -> Optional[TimetableSlot]:
        return (
            await db.execute(
                select(TimetableSlot).where(
                    TimetableSlot.faculty_credential_id == faculty_credential_id,
                    TimetableSlot.academic_year == academic_year,
                    TimetableSlot.academic_year == academic_year,
                    TimetableSlot.calendar_date == lecture_date,
                    TimetableSlot.slot_number == slot_number,
                    TimetableSlot.is_active.is_(True),
                )
            )
        ).scalars().first()

    async def _get_day_scheduled_count(
        self,
        db: AsyncSession,
        faculty_credential_id: UUID,
        academic_year: str,
        attendance_date: date,
    ) -> int:
        return int(
            (
                await db.execute(
                    select(func.count(TimetableSlot.id)).where(
                        TimetableSlot.faculty_credential_id == faculty_credential_id,
                        TimetableSlot.academic_year == academic_year,
                        TimetableSlot.academic_year == academic_year,
                        TimetableSlot.calendar_date == attendance_date,
                        TimetableSlot.is_active.is_(True),
                    )
                )
            ).scalar_one()
            or 0
        )

    async def create_timetable(
        self, db: AsyncSession, current_user: User, req: TimetableSlotCreateRequest
    ) -> list[TimetableSlot]:
        """Create timetable slots for a faculty credential."""
        credential = await self._get_credential_or_404(db, req.faculty_credential_id)
        await self._ensure_credential_active(credential)
        await self._ensure_principal_scope(current_user, credential.institution_id)

        appointment = await self._get_accepted_appointment(db, credential)

        created_slots: list[TimetableSlot] = []
        for slot in req.slots:
            if slot.start_time >= slot.end_time:
                self._raise_error(400, "INVALID_DATE_RANGE", "start_time must be before end_time")
            overlap = (
                await db.execute(
                    select(TimetableSlot).where(
                        TimetableSlot.faculty_credential_id == req.faculty_credential_id,
                        TimetableSlot.calendar_date == slot.calendar_date,
                        TimetableSlot.academic_year == req.academic_year,
                        TimetableSlot.is_active.is_(True),
                        TimetableSlot.start_time < slot.end_time,
                        TimetableSlot.end_time > slot.start_time,
                    )
                )
            ).scalars().first()
            if overlap:
                self._raise_error(409, "INTEGRITY_ERROR", "Overlapping timetable slot exists for this faculty")

            created = TimetableSlot(
                institution_id=credential.institution_id,
                course_id=appointment.course_id,
                faculty_credential_id=req.faculty_credential_id,
                academic_year=req.academic_year,
                calendar_date=slot.calendar_date,
                slot_number=slot.slot_number,
                start_time=slot.start_time,
                end_time=slot.end_time,
                subject_name=slot.subject_name,
                lecture_type=slot.lecture_type,
                class_name=slot.class_name,
                is_active=True,
                created_by=current_user.id,
            )
            db.add(created)
            created_slots.append(created)

        await db.flush()
        for slot in created_slots:
            await self._write_audit_log(
                db,
                "TimetableSlot",
                self._entity_id_from_uuid(slot.id),
                "CREATE",
                current_user.id,
                new_value={
                    "faculty_credential_id": str(slot.faculty_credential_id),
                    "calendar_date": slot.calendar_date.isoformat(),
                    "slot_number": slot.slot_number,
                    "academic_year": slot.academic_year,
                },
            )
        await db.commit()
        return created_slots

    async def get_timetable(
        self,
        db: AsyncSession,
        current_user: User,
        faculty_credential_id: Optional[UUID],
        academic_year: str,
    ) -> dict[str, list[dict[str, Any]]]:
        """Return weekly timetable grouped by day."""
        resolved_credential_id = faculty_credential_id
        if current_user.role == RoleEnum.FACULTY:
            own_credential, _ = await self._get_faculty_context(db, current_user)
            if resolved_credential_id and own_credential.id != resolved_credential_id:
                self._raise_error(403, "UNAUTHORIZED_ACCESS", "Faculty can view only their own timetable")
            resolved_credential_id = own_credential.id
        elif current_user.role == RoleEnum.PRINCIPAL:
            if not resolved_credential_id:
                self._raise_error(400, "HTTP_ERROR", "faculty_credential_id is required")
            credential = await self._get_credential_or_404(db, resolved_credential_id)
            await self._ensure_principal_scope(current_user, credential.institution_id)

        rows = (
            await db.execute(
                select(TimetableSlot)
                .where(
                    TimetableSlot.faculty_credential_id == resolved_credential_id,
                    TimetableSlot.academic_year == academic_year,
                )
                .order_by(TimetableSlot.calendar_date.asc(), TimetableSlot.slot_number.asc())
            )
        ).scalars().all()

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[row.calendar_date.isoformat()].append(TimetableSlotResponse.model_validate(row, from_attributes=True).model_dump())
        return dict(grouped)

    async def update_timetable_slot(
        self, db: AsyncSession, current_user: User, slot_id: UUID, req: TimetableSlotUpdateRequest
    ) -> TimetableSlot:
        """Update an existing timetable slot if it is not already in active use."""
        slot = (await db.execute(select(TimetableSlot).where(TimetableSlot.id == slot_id))).scalars().first()
        if not slot:
            self._raise_error(404, "NOT_FOUND", "Timetable slot not found")
        await self._ensure_principal_scope(current_user, slot.institution_id)

        in_use = (
            await db.execute(
                select(func.count(LectureLog.id)).where(
                    LectureLog.timetable_slot_id == slot.id,
                    extract("month", LectureLog.lecture_date) == date.today().month,
                    extract("year", LectureLog.lecture_date) == date.today().year,
                )
            )
        ).scalar_one()
        if in_use:
            self._raise_error(403, "TIMETABLE_SLOT_IN_USE", "Timetable slot already has lecture logs this month")

        old_values = {
            "start_time": str(slot.start_time),
            "end_time": str(slot.end_time),
            "subject_name": slot.subject_name,
            "lecture_type": slot.lecture_type,
            "class_name": slot.class_name,
            "is_active": slot.is_active,
        }
        for field in ["start_time", "end_time", "subject_name", "lecture_type", "class_name", "is_active"]:
            value = getattr(req, field)
            if value is not None:
                setattr(slot, field, value)
        if slot.start_time >= slot.end_time:
            self._raise_error(400, "INVALID_DATE_RANGE", "start_time must be before end_time")

        await self._write_audit_log(
            db,
            "TimetableSlot",
            self._entity_id_from_uuid(slot.id),
            "UPDATE",
            current_user.id,
            old_value=old_values,
            new_value={
                "start_time": str(slot.start_time),
                "end_time": str(slot.end_time),
                "subject_name": slot.subject_name,
                "lecture_type": slot.lecture_type,
                "class_name": slot.class_name,
                "is_active": slot.is_active,
            },
        )
        await db.commit()
        return slot

    async def upsert_calendar(
        self, db: AsyncSession, current_user: User, institution_id: int, academic_year: str, entries: list[CalendarEntryRequest]
    ) -> list[AcademicCalendar]:
        """Bulk upsert academic calendar rows."""
        if current_user.role == RoleEnum.PRINCIPAL:
            await self._ensure_principal_scope(current_user, institution_id)

        result_rows: list[AcademicCalendar] = []
        for entry in entries:
            existing = (
                await db.execute(
                    select(AcademicCalendar).where(
                        AcademicCalendar.institution_id == institution_id,
                        AcademicCalendar.academic_year == academic_year,
                        AcademicCalendar.calendar_date == entry.calendar_date,
                    )
                )
            ).scalars().first()
            if existing:
                old_value = {"day_type": existing.day_type, "description": existing.description}
                existing.day_type = entry.day_type
                existing.description = entry.description
                row = existing
                await self._write_audit_log(
                    db,
                    "AcademicCalendar",
                    self._entity_id_from_uuid(existing.id),
                    "UPDATE",
                    current_user.id,
                    old_value=old_value,
                    new_value={"day_type": existing.day_type, "description": existing.description},
                )
            else:
                row = AcademicCalendar(
                    institution_id=institution_id,
                    academic_year=academic_year,
                    calendar_date=entry.calendar_date,
                    day_type=entry.day_type,
                    description=entry.description,
                    created_by=current_user.id,
                )
                db.add(row)
                await db.flush()
                await self._write_audit_log(
                    db,
                    "AcademicCalendar",
                    self._entity_id_from_uuid(row.id),
                    "CREATE",
                    current_user.id,
                    new_value={"day_type": row.day_type, "description": row.description},
                )
            result_rows.append(row)

        await db.commit()
        return result_rows

    async def get_calendar(
        self,
        db: AsyncSession,
        current_user: User,
        institution_id: Optional[int],
        academic_year: str,
        month: Optional[int],
    ) -> list[dict[str, Any]]:
        """Fetch academic calendar entries for the requested period."""
        resolved_institution_id = institution_id
        if current_user.role == RoleEnum.FACULTY:
            credential, _ = await self._get_faculty_context(db, current_user)
            resolved_institution_id = credential.institution_id
        if resolved_institution_id is None:
            self._raise_error(400, "HTTP_ERROR", "institution_id is required")
        if current_user.role == RoleEnum.PRINCIPAL:
            await self._ensure_principal_scope(current_user, resolved_institution_id)

        stmt = select(AcademicCalendar).where(
            AcademicCalendar.institution_id == resolved_institution_id,
            AcademicCalendar.academic_year == academic_year,
        )
        if month:
            stmt = stmt.where(extract("month", AcademicCalendar.calendar_date) == month)
        rows = (await db.execute(stmt.order_by(AcademicCalendar.calendar_date.asc()))).scalars().all()

        return [
            CalendarEntryResponse(
                id=row.id,
                institution_id=row.institution_id,
                academic_year=row.academic_year,
                calendar_date=row.calendar_date,
                day_type=row.day_type,
                description=row.description,
                is_holiday=row.day_type == CalendarDayType.HOLIDAY.value,
                is_exam=row.day_type == CalendarDayType.EXAM.value,
            ).model_dump()
            for row in rows
        ]

    async def _build_faculty_log_payload(
        self,
        db: AsyncSession,
        current_user: User,
        req: LectureLogCreateRequest,
    ) -> tuple[FacultyCredentials, AppointmentLetter, Optional[TimetableSlot], Optional[DailyAttendanceSummary]]:
        credential, appointment = await self._get_faculty_context(db, current_user)
        await self._ensure_credential_active(credential)

        calendar_entry = await self._get_calendar_entry(db, credential.institution_id, appointment.academic_year, req.lecture_date)
        if calendar_entry and calendar_entry.day_type == CalendarDayType.HOLIDAY.value:
            self._raise_error(400, "CANNOT_LOG_ON_HOLIDAY", "Lecture logs cannot be created on holidays")
        summary = await self._get_summary(db, credential.id, req.lecture_date)
        if summary and summary.is_locked:
            self._raise_error(403, "ATTENDANCE_PERIOD_LOCKED", "Attendance period is locked for this date")
        slot = None
        if req.is_substitute and not req.substitute_for_faculty_id:
            self._raise_error(400, "SUBSTITUTE_FACULTY_REQUIRED", "Substitute faculty must be specified")
        if not req.is_extra:
            slot = await self._get_slot_match(db, credential.id, appointment.academic_year, req.lecture_date, req.slot_number)
        return credential, appointment, slot, summary

    async def create_log(
        self,
        db: AsyncSession,
        current_user: User,
        req: LectureLogCreateRequest,
    ) -> LectureLog:
        """Create a draft lecture log for the current faculty user."""
        credential, appointment, slot, _ = await self._build_faculty_log_payload(db, current_user, req)
        duplicate = (
            await db.execute(
                select(LectureLog.id).where(
                    LectureLog.faculty_credential_id == credential.id,
                    LectureLog.lecture_date == req.lecture_date,
                    LectureLog.slot_number == req.slot_number,
                )
            )
        ).scalar_one_or_none()
        if duplicate:
            self._raise_error(409, "SLOT_ALREADY_LOGGED", "A lecture log already exists for this slot")

        start_time = slot.start_time if slot else time(hour=8 + (req.slot_number - 1))
        end_time = slot.end_time if slot else time(hour=min(start_time.hour + 1, 23))
        lecture_type = (
            LectureLogType.SUBSTITUTE.value
            if req.is_substitute
            else LectureLogType.EXTRA.value
            if req.is_extra
            else req.lecture_type
        )
        lecture_log = LectureLog(
            faculty_credential_id=credential.id,
            timetable_slot_id=None if req.is_extra else (slot.id if slot else None),
            institution_id=credential.institution_id,
            course_id=appointment.course_id,
            academic_year=appointment.academic_year,
            lecture_date=req.lecture_date,
            slot_number=req.slot_number,
            start_time=start_time,
            end_time=end_time,
            subject_name=req.subject_name,
            lecture_type=lecture_type,
            class_name=req.class_name,
            topic_covered=req.topic_covered,
            attendance_count=req.attendance_count,
            latitude=req.latitude,
            longitude=req.longitude,
            is_extra=req.is_extra,
            is_substitute=req.is_substitute,
            substitute_for_faculty_id=req.substitute_for_faculty_id,
            log_status=LectureLogStatus.DRAFT.value,
        )
        db.add(lecture_log)
        await db.flush()
        await self.compute_daily_summary(credential.id, req.lecture_date, db)
        await self._write_lecture_log_audit(db, lecture_log.id, LectureLogAuditAction.CREATED, current_user.id)
        await self._write_audit_log(
            db,
            "LectureLog",
            self._entity_id_from_uuid(lecture_log.id),
            "CREATE",
            current_user.id,
            new_value={"slot_number": lecture_log.slot_number, "lecture_date": str(lecture_log.lecture_date)},
        )
        await db.commit()
        return lecture_log

    async def update_log(
        self,
        db: AsyncSession,
        current_user: User,
        log_id: UUID,
        req: LectureLogUpdateRequest,
    ) -> LectureLog:
        """Update an editable draft or rejected lecture log."""
        own_credential, _ = await self._get_faculty_context(db, current_user)
        lecture_log = await self._get_log_or_404(db, log_id)
        if lecture_log.faculty_credential_id != own_credential.id:
            self._raise_error(403, "UNAUTHORIZED_ACCESS", "Faculty can edit only their own logs")
        if lecture_log.log_status not in {LectureLogStatus.DRAFT.value, LectureLogStatus.REJECTED.value}:
            self._raise_error(403, "LOG_NOT_EDITABLE", "Only draft or rejected logs can be edited")
        summary = await self._get_summary(db, lecture_log.faculty_credential_id, lecture_log.lecture_date)
        if summary and summary.is_locked:
            self._raise_error(403, "ATTENDANCE_PERIOD_LOCKED", "Attendance period is locked for this date")

        old_values = {
            "topic_covered": lecture_log.topic_covered,
            "attendance_count": lecture_log.attendance_count,
            "subject_name": lecture_log.subject_name,
            "lecture_type": lecture_log.lecture_type,
            "class_name": lecture_log.class_name,
        }
        for field in ["topic_covered", "attendance_count", "subject_name", "lecture_type", "class_name"]:
            value = getattr(req, field)
            if value is not None:
                setattr(lecture_log, field, value)
        lecture_log.rejection_reason = None
        await self._write_lecture_log_audit(db, lecture_log.id, LectureLogAuditAction.EDITED, current_user.id)
        await self._write_audit_log(
            db,
            "LectureLog",
            self._entity_id_from_uuid(lecture_log.id),
            "UPDATE",
            current_user.id,
            old_value=old_values,
            new_value={
                "topic_covered": lecture_log.topic_covered,
                "attendance_count": lecture_log.attendance_count,
                "subject_name": lecture_log.subject_name,
                "lecture_type": lecture_log.lecture_type,
                "class_name": lecture_log.class_name,
            },
        )
        await db.commit()
        return lecture_log

    async def submit_log(self, db: AsyncSession, current_user: User, log_id: UUID) -> LectureLog:
        """Submit a faculty lecture log for principal review."""
        own_credential, _ = await self._get_faculty_context(db, current_user)
        lecture_log = await self._get_log_or_404(db, log_id)
        if lecture_log.faculty_credential_id != own_credential.id:
            self._raise_error(403, "UNAUTHORIZED_ACCESS", "Faculty can submit only their own logs")
        if lecture_log.log_status not in {LectureLogStatus.DRAFT.value, LectureLogStatus.REJECTED.value}:
            self._raise_error(403, "LOG_NOT_EDITABLE", "Only draft or rejected logs can be submitted")
        summary = await self._get_summary(db, lecture_log.faculty_credential_id, lecture_log.lecture_date)
        if summary and summary.is_locked:
            self._raise_error(403, "ATTENDANCE_PERIOD_LOCKED", "Attendance period is locked for this date")
        if not lecture_log.topic_covered.strip():
            self._raise_error(400, "TOPIC_REQUIRED", "Topic covered is required")
        if lecture_log.attendance_count is not None and not (0 <= lecture_log.attendance_count <= 100):
            self._raise_error(400, "HTTP_ERROR", "attendance_count must be between 0 and 100")

        lecture_log.log_status = LectureLogStatus.SUBMITTED.value
        lecture_log.submitted_at = datetime.utcnow()
        await self.compute_daily_summary(lecture_log.faculty_credential_id, lecture_log.lecture_date, db)
        await self._write_lecture_log_audit(db, lecture_log.id, LectureLogAuditAction.SUBMITTED, current_user.id)
        await self._write_audit_log(
            db,
            "LectureLog",
            self._entity_id_from_uuid(lecture_log.id),
            "SUBMIT",
            current_user.id,
            new_value={"log_status": lecture_log.log_status, "submitted_at": lecture_log.submitted_at.isoformat()},
        )
        await db.commit()
        return lecture_log

    async def verify_log(
        self,
        db: AsyncSession,
        current_user: User,
        log_id: UUID,
        action: str,
        remarks: Optional[str],
    ) -> LectureLog:
        """Verify or reject a submitted lecture log."""
        lecture_log = await self._get_log_or_404(db, log_id)
        await self._ensure_principal_scope(current_user, lecture_log.institution_id)
        if lecture_log.log_status != LectureLogStatus.SUBMITTED.value:
            self._raise_error(400, "HTTP_ERROR", "Only submitted logs can be verified")
        if action not in {"VERIFY", "REJECT"}:
            self._raise_error(400, "HTTP_ERROR", "action must be VERIFY or REJECT")

        if action == "VERIFY":
            lecture_log.log_status = LectureLogStatus.VERIFIED.value
            lecture_log.verified_by = current_user.id
            lecture_log.verified_at = datetime.utcnow()
            audit_action = LectureLogAuditAction.VERIFIED
        else:
            if not remarks:
                self._raise_error(400, "HTTP_ERROR", "remarks are required when rejecting a log")
            lecture_log.log_status = LectureLogStatus.REJECTED.value
            lecture_log.rejection_reason = remarks
            audit_action = LectureLogAuditAction.REJECTED

        await self.compute_daily_summary(lecture_log.faculty_credential_id, lecture_log.lecture_date, db)
        await self._write_lecture_log_audit(db, lecture_log.id, audit_action, current_user.id, remarks=remarks)
        await self._write_audit_log(
            db,
            "LectureLog",
            self._entity_id_from_uuid(lecture_log.id),
            audit_action.value,
            current_user.id,
            new_value={"log_status": lecture_log.log_status, "remarks": remarks},
        )
        await db.commit()
        return lecture_log

    async def list_logs(
        self,
        db: AsyncSession,
        current_user: User,
        faculty_credential_id: Optional[UUID],
        month: Optional[int],
        year: Optional[int],
        academic_year: Optional[str],
        log_status: Optional[str],
        course_id: Optional[int],
        skip: int = 0,
        limit: int = 10,
    ) -> tuple[list[dict[str, Any]], int]:
        """List lecture logs with related slot, anomaly, and daily-summary context."""
        resolved_credential_id = faculty_credential_id
        institution_scope: Optional[int] = None
        if current_user.role == RoleEnum.FACULTY:
            own_credential, _ = await self._get_faculty_context(db, current_user)
            resolved_credential_id = own_credential.id
        elif current_user.role == RoleEnum.PRINCIPAL:
            institution_scope = current_user.institution_id

        stmt = select(LectureLog).order_by(LectureLog.lecture_date.desc(), LectureLog.slot_number.asc())
        if resolved_credential_id:
            stmt = stmt.where(LectureLog.faculty_credential_id == resolved_credential_id)
        if month:
            stmt = stmt.where(extract("month", LectureLog.lecture_date) == month)
        if year:
            stmt = stmt.where(extract("year", LectureLog.lecture_date) == year)
        if academic_year:
            stmt = stmt.where(LectureLog.academic_year == academic_year)
        if log_status:
            stmt = stmt.where(LectureLog.log_status == log_status)
        if course_id:
            stmt = stmt.where(LectureLog.course_id == course_id)
        if institution_scope:
            stmt = stmt.where(LectureLog.institution_id == institution_scope)

        from sqlalchemy import func
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(LectureLog.lecture_date.desc(), LectureLog.slot_number.asc())
        if limit > 0:
            stmt = stmt.offset(skip).limit(limit)

        logs = (await db.execute(stmt)).scalars().all()
        log_ids = [log.id for log in logs]
        slot_ids = [log.timetable_slot_id for log in logs if log.timetable_slot_id]

        slots = (
            await db.execute(select(TimetableSlot).where(TimetableSlot.id.in_(slot_ids)))
        ).scalars().all() if slot_ids else []
        slot_map = {slot.id: slot for slot in slots}

        anomalies = (
            await db.execute(select(AttendanceAnomaly).where(AttendanceAnomaly.lecture_log_id.in_(log_ids)))
        ).scalars().all() if log_ids else []
        anomaly_map: dict[UUID, list[AttendanceAnomaly]] = defaultdict(list)
        for anomaly in anomalies:
            anomaly_map[anomaly.lecture_log_id].append(anomaly)

        summary_keys = {(log.faculty_credential_id, log.lecture_date) for log in logs}
        summaries: dict[tuple[UUID, date], DailyAttendanceSummary] = {}
        if summary_keys:
            summary_rows = (
                await db.execute(
                    select(DailyAttendanceSummary).where(
                        tuple_(DailyAttendanceSummary.faculty_credential_id, DailyAttendanceSummary.attendance_date).in_(summary_keys)
                    )
                )
            ).scalars().all()
            summaries = {(row.faculty_credential_id, row.attendance_date): row for row in summary_rows}

        payload = []
        for log in logs:
            item = LectureLogResponse(
                **{
                    **log.__dict__,
                    "timetable_slot": TimetableSlotResponse.model_validate(slot_map[log.timetable_slot_id], from_attributes=True).model_dump()
                    if log.timetable_slot_id and log.timetable_slot_id in slot_map
                    else None,
                    "anomaly_flags": [
                        {
                            "id": anomaly.id,
                            "anomaly_type": anomaly.anomaly_type,
                            "severity": anomaly.severity,
                            "description": anomaly.description,
                            "is_acknowledged": anomaly.is_acknowledged,
                            "created_at": anomaly.created_at,
                        }
                        for anomaly in anomaly_map.get(log.id, [])
                    ],
                    "daily_summary": DailyAttendanceSummaryResponse.model_validate(
                        summaries.get((log.faculty_credential_id, log.lecture_date)), from_attributes=True
                    ).model_dump()
                    if summaries.get((log.faculty_credential_id, log.lecture_date))
                    else None,
                }
            )
            payload.append(item.model_dump())
        return payload, total

    async def get_monthly_summary(
        self,
        db: AsyncSession,
        current_user: User,
        faculty_credential_id: Optional[UUID],
        academic_year: str,
        month: int,
    ) -> dict[str, int]:
        """Return monthly attendance totals for billing-facing reporting."""
        # STEP 8 GATE: This monthly summary feeds bill generation.
        resolved_credential_id = faculty_credential_id
        institution_scope: Optional[int] = None
        if current_user.role == RoleEnum.FACULTY:
            own_credential, _ = await self._get_faculty_context(db, current_user)
            resolved_credential_id = own_credential.id
        elif current_user.role == RoleEnum.PRINCIPAL:
            institution_scope = current_user.institution_id

        if not resolved_credential_id:
            self._raise_error(400, "HTTP_ERROR", "faculty_credential_id is required")
        stmt = select(DailyAttendanceSummary).where(
            DailyAttendanceSummary.faculty_credential_id == resolved_credential_id,
            DailyAttendanceSummary.academic_year == academic_year,
            extract("month", DailyAttendanceSummary.attendance_date) == month,
        )
        if institution_scope:
            stmt = stmt.where(DailyAttendanceSummary.institution_id == institution_scope)
        rows = (await db.execute(stmt)).scalars().all()

        anomaly_count = int(
            (
                await db.execute(
                    select(func.count(AttendanceAnomaly.id))
                    .where(AttendanceAnomaly.faculty_credential_id == resolved_credential_id)
                    .join(LectureLog, LectureLog.id == AttendanceAnomaly.lecture_log_id, isouter=True)
                    .where(
                        or_(
                            LectureLog.id.is_(None),
                            extract("month", LectureLog.lecture_date) == month,
                        )
                    )
                )
            ).scalar_one()
            or 0
        )

        return {
            "total_scheduled": sum(row.scheduled_lectures for row in rows),
            "total_conducted": sum(row.conducted_lectures for row in rows),
            "total_extra": sum(row.extra_lectures for row in rows),
            "total_substitute": sum(row.substitute_lectures for row in rows),
            "total_billable": sum(row.total_billable_lectures for row in rows),
            "present_days": sum(1 for row in rows if row.is_present),
            "absent_days": sum(1 for row in rows if not row.is_present and not row.is_holiday),
            "anomaly_count": anomaly_count,
        }

    async def list_anomalies(
        self,
        db: AsyncSession,
        current_user: User,
        faculty_credential_id: Optional[UUID],
        severity: Optional[str],
        is_acknowledged: Optional[bool],
        institution_id: Optional[int],
        month: Optional[int],
        year: Optional[int],
        skip: int = 0,
        limit: int = 10,
    ) -> tuple[list[dict[str, Any]], int]:
        """List attendance anomalies with linked lecture-log context."""
        resolved_institution_id = institution_id
        if current_user.role == RoleEnum.PRINCIPAL:
            resolved_institution_id = current_user.institution_id

        stmt = select(AttendanceAnomaly, LectureLog).outerjoin(LectureLog, LectureLog.id == AttendanceAnomaly.lecture_log_id)
        if faculty_credential_id:
            stmt = stmt.where(AttendanceAnomaly.faculty_credential_id == faculty_credential_id)
        if severity:
            stmt = stmt.where(AttendanceAnomaly.severity == severity)
        if is_acknowledged is not None:
            stmt = stmt.where(AttendanceAnomaly.is_acknowledged == is_acknowledged)
        if resolved_institution_id:
            stmt = stmt.where(AttendanceAnomaly.institution_id == resolved_institution_id)
        if month:
            stmt = stmt.where(
                or_(
                    AttendanceAnomaly.lecture_log_id.is_(None),
                    extract("month", LectureLog.lecture_date) == month,
                )
            )
        if year:
            stmt = stmt.where(
                or_(
                    AttendanceAnomaly.lecture_log_id.is_(None),
                    extract("year", LectureLog.lecture_date) == year,
                )
            )
            
        from sqlalchemy import func
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(AttendanceAnomaly.created_at.desc())
        if limit > 0:
            stmt = stmt.offset(skip).limit(limit)
            
        rows = (await db.execute(stmt)).all()
        payload = []
        for anomaly, log in rows:
            payload.append(
                AnomalyResponse(
                    id=anomaly.id,
                    faculty_credential_id=anomaly.faculty_credential_id,
                    lecture_log_id=anomaly.lecture_log_id,
                    summary_id=anomaly.summary_id,
                    institution_id=anomaly.institution_id,
                    anomaly_type=anomaly.anomaly_type,
                    severity=anomaly.severity,
                    description=anomaly.description,
                    is_acknowledged=anomaly.is_acknowledged,
                    acknowledged_by=anomaly.acknowledged_by,
                    acknowledged_at=anomaly.acknowledged_at,
                    acknowledgement_remarks=anomaly.acknowledgement_remarks,
                    created_at=anomaly.created_at,
                    lecture_log={
                        "id": log.id,
                        "lecture_date": log.lecture_date,
                        "slot_number": log.slot_number,
                        "subject_name": log.subject_name,
                        "log_status": log.log_status,
                    }
                    if log
                    else None,
                ).model_dump()
            )
        return payload, total

    async def acknowledge_anomaly(
        self,
        db: AsyncSession,
        current_user: User,
        anomaly_id: UUID,
        remarks: str,
    ) -> AttendanceAnomaly:
        """Acknowledge an anomaly as principal."""
        anomaly = (
            await db.execute(select(AttendanceAnomaly).where(AttendanceAnomaly.id == anomaly_id))
        ).scalars().first()
        if not anomaly:
            self._raise_error(404, "NOT_FOUND", "Anomaly not found")
        await self._ensure_principal_scope(current_user, anomaly.institution_id)
        anomaly.is_acknowledged = True
        anomaly.acknowledged_by = current_user.id
        anomaly.acknowledged_at = datetime.utcnow()
        anomaly.acknowledgement_remarks = remarks
        await self._write_audit_log(
            db,
            "AttendanceAnomaly",
            self._entity_id_from_uuid(anomaly.id),
            "ACKNOWLEDGE",
            current_user.id,
            new_value={"remarks": remarks},
        )
        await db.commit()
        return anomaly

    async def bulk_submit(
        self,
        db: AsyncSession,
        current_user: User,
        log_ids: list[UUID],
    ) -> dict[str, Any]:
        """Submit multiple lecture logs, collecting per-log failures."""
        success_count = 0
        failed: list[dict[str, Any]] = []
        for log_id in log_ids:
            try:
                await self.submit_log(db, current_user, log_id)
                success_count += 1
            except HTTPException as exc:
                detail = exc.detail if isinstance(exc.detail, dict) else {}
                failed.append({"log_id": log_id, "reason": detail.get("code", "HTTP_ERROR")})
                await db.rollback()
        return {"success_count": success_count, "failed": failed}

    async def compute_daily_summary(
        self,
        faculty_credential_id: UUID,
        attendance_date: date,
        db: AsyncSession,
    ) -> DailyAttendanceSummary:
        """Compute and upsert the faculty daily attendance summary for one date."""
        logs = (
            await db.execute(
                select(LectureLog).where(
                    LectureLog.faculty_credential_id == faculty_credential_id,
                    LectureLog.lecture_date == attendance_date,
                    LectureLog.log_status.in_([LectureLogStatus.SUBMITTED.value, LectureLogStatus.VERIFIED.value]),
                )
            )
        ).scalars().all()
        any_log = (
            await db.execute(
                select(LectureLog).where(
                    LectureLog.faculty_credential_id == faculty_credential_id,
                    LectureLog.lecture_date == attendance_date,
                )
            )
        ).scalars().first()
        if any_log:
            institution_id = any_log.institution_id
            course_id = any_log.course_id
            academic_year = any_log.academic_year
        else:
            credential = await self._get_credential_or_404(db, faculty_credential_id)
            appointment = await self._get_accepted_appointment(db, credential)
            institution_id = credential.institution_id
            course_id = appointment.course_id
            academic_year = appointment.academic_year

        conducted = len([log for log in logs if not log.is_extra and not log.is_substitute])
        extra = len([log for log in logs if log.is_extra])
        substitute = len([log for log in logs if log.is_substitute])
        scheduled = await self._get_day_scheduled_count(db, faculty_credential_id, academic_year, attendance_date)
        calendar_entry = await self._get_calendar_entry(db, institution_id, academic_year, attendance_date)
        is_holiday = bool(calendar_entry and calendar_entry.day_type == CalendarDayType.HOLIDAY.value)
        total_billable = min(conducted + extra + substitute, settings.MAX_DAILY_LECTURES_POLICY)

        summary = await self._get_summary(db, faculty_credential_id, attendance_date)
        if not summary:
            summary = DailyAttendanceSummary(
                faculty_credential_id=faculty_credential_id,
                institution_id=institution_id,
                course_id=course_id,
                academic_year=academic_year,
                attendance_date=attendance_date,
            )
            db.add(summary)

        summary.scheduled_lectures = scheduled
        summary.conducted_lectures = conducted
        summary.extra_lectures = extra
        summary.substitute_lectures = substitute
        summary.total_billable_lectures = total_billable
        summary.is_present = conducted > 0
        summary.is_holiday = is_holiday
        # STEP 8 GATE: is_locked is set exclusively by bill generation service.
        await db.flush()
        return summary

    async def process_log_anomalies(self, log_id: UUID, actor_user_id: int) -> None:
        """Run the anomaly engine and persist returned anomalies for one lecture log."""
        async with AsyncSessionLocal() as db:
            lecture_log = await self._get_log_or_404(db, log_id)
            recent_from = lecture_log.lecture_date.replace(day=1) - timedelta(days=30)
            recent_logs = (
                await db.execute(
                    select(LectureLog).where(
                        LectureLog.faculty_credential_id == lecture_log.faculty_credential_id,
                        LectureLog.lecture_date >= recent_from,
                        LectureLog.lecture_date <= lecture_log.lecture_date,
                    )
                )
            ).scalars().all()
            timetable_rows = (
                await db.execute(
                    select(TimetableSlot).where(
                        TimetableSlot.faculty_credential_id == lecture_log.faculty_credential_id,
                        TimetableSlot.academic_year == lecture_log.academic_year,
                    )
                )
            ).scalars().all()
            calendar_rows = (
                await db.execute(
                    select(AcademicCalendar).where(
                        AcademicCalendar.institution_id == lecture_log.institution_id,
                        AcademicCalendar.academic_year == lecture_log.academic_year,
                        AcademicCalendar.calendar_date >= recent_from,
                        AcademicCalendar.calendar_date <= lecture_log.lecture_date,
                    )
                )
            ).scalars().all()
            summary = await self._get_summary(db, lecture_log.faculty_credential_id, lecture_log.lecture_date)

            existing = (
                await db.execute(select(AttendanceAnomaly).where(AttendanceAnomaly.lecture_log_id == lecture_log.id))
            ).scalars().all()
            for anomaly in existing:
                await db.delete(anomaly)
            await db.flush()

            engine_anomalies = run_attendance_anomaly_check(
                faculty_credential_id=lecture_log.faculty_credential_id,
                lecture_log=LectureLogInput(
                    faculty_credential_id=lecture_log.faculty_credential_id,
                    lecture_date=lecture_log.lecture_date,
                    calendar_date=lecture_log.lecture_date,
                    slot_number=lecture_log.slot_number,
                    subject_name=lecture_log.subject_name,
                    topic_covered=lecture_log.topic_covered,
                    attendance_count=lecture_log.attendance_count,
                    class_name=lecture_log.class_name,
                    created_at=lecture_log.created_at or datetime.utcnow(),
                    log_status=lecture_log.log_status,
                    period_locked=bool(summary and summary.is_locked),
                ),
                recent_logs=[
                    LectureLogInput(
                        faculty_credential_id=row.faculty_credential_id,
                        lecture_date=row.lecture_date,
                        calendar_date=row.lecture_date,
                        slot_number=row.slot_number,
                        subject_name=row.subject_name,
                        topic_covered=row.topic_covered,
                        attendance_count=row.attendance_count,
                        class_name=row.class_name,
                        created_at=row.created_at or datetime.utcnow(),
                        log_status=row.log_status,
                        period_locked=bool(summary and summary.is_locked and row.lecture_date == lecture_log.lecture_date),
                    )
                    for row in recent_logs
                ],
                timetable_slots=[
                    TimetableSlotInput(
                        calendar_date=row.calendar_date,
                        slot_number=row.slot_number,
                        subject_name=row.subject_name,
                        class_name=row.class_name,
                        is_active=row.is_active,
                    )
                    for row in timetable_rows
                ],
                calendar_entries=[
                    CalendarEntry(
                        calendar_date=row.calendar_date,
                        day_type=row.day_type,
                        description=row.description,
                    )
                    for row in calendar_rows
                ],
            )

            has_high = False
            for item in engine_anomalies:
                anomaly = AttendanceAnomaly(
                    faculty_credential_id=lecture_log.faculty_credential_id,
                    lecture_log_id=lecture_log.id,
                    summary_id=summary.id if summary else None,
                    institution_id=lecture_log.institution_id,
                    anomaly_type=item.anomaly_type,
                    severity=item.severity,
                    description=item.description,
                )
                db.add(anomaly)
                await db.flush()
                await self._write_lecture_log_audit(
                    db,
                    lecture_log.id,
                    LectureLogAuditAction.ANOMALY_DETECTED,
                    actor_user_id,
                    remarks=item.description,
                )
                await self._write_audit_log(
                    db,
                    "AttendanceAnomaly",
                    self._entity_id_from_uuid(anomaly.id),
                    "CREATE",
                    actor_user_id,
                    new_value={"anomaly_type": item.anomaly_type, "severity": item.severity},
                )
                if item.severity == AnomalySeverity.HIGH.value:
                    has_high = True

            # STEP 8 GATE: HIGH severity anomalies must be acknowledged before bill generation is allowed.
            if has_high:
                lecture_log.log_status = LectureLogStatus.FLAGGED.value
                await self._write_lecture_log_audit(
                    db,
                    lecture_log.id,
                    LectureLogAuditAction.FLAGGED,
                    actor_user_id,
                    remarks="High severity anomaly detected",
                )
                await self._write_audit_log(
                    db,
                    "LectureLog",
                    self._entity_id_from_uuid(lecture_log.id),
                    "FLAGGED",
                    actor_user_id,
                    new_value={"log_status": lecture_log.log_status},
                )
            await db.commit()
