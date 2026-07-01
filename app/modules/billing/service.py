from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, delete, extract, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.appointment_letter import AppointmentLetter
from app.models.attendance_anomaly import AnomalySeverity, AttendanceAnomaly
from app.models.audit import AuditLog
from app.models.bill_approval import BillApproval, BillApprovalAction
from app.models.bill_audit import BillAudit, BillAuditAction
from app.models.bill_line_item import BillLineItem
from app.models.chb_bill import BillApproverRole, BillStatus, CHBBill
from app.models.daily_attendance_summary import DailyAttendanceSummary
from app.models.faculty_credentials import FacultyCredentials
from app.models.institution import Institution
from app.models.lecture_log import LectureLog, LectureLogStatus
from app.models.rate_master import RateMaster, CHBDesignation, RateLectureType
from app.models.user import RoleEnum, User
from app.modules.billing import bill_calculator
from app.modules.billing.bill_calculator import BillCalculationError, BillCalculationInput, LectureLogInput
from app.modules.billing.schemas import (
    BillApprovalRequest,
    BillLineItemResponse,
    CHBBillResponse,
)


class BillingService:
    """Business logic for Step 8 CHB bill generation and approvals."""

    @staticmethod
    def _raise_error(status_code: int, code: str, message: str) -> None:
        raise HTTPException(status_code=status_code, detail={"code": code, "message": message})

    @staticmethod
    def _entity_id_from_uuid(value: UUID) -> str:
        return str(value)

    @staticmethod
    def _enum_value(value: Any) -> str:
        return value.value if hasattr(value, "value") else str(value)

    @staticmethod
    def _normalize_designation(value: str) -> str:
        return value.strip().upper().replace(" ", "_").replace("-", "_")

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

    async def _write_bill_audit(
        self,
        db: AsyncSession,
        bill_id: UUID,
        action: BillAuditAction,
        performed_by: int,
        old_status: Optional[str] = None,
        new_status: Optional[str] = None,
        remarks: Optional[str] = None,
    ) -> None:
        db.add(
            BillAudit(
                bill_id=bill_id,
                action=action.value,
                performed_by=performed_by,
                old_status=old_status,
                new_status=new_status,
                remarks=remarks,
            )
        )

    async def _get_faculty_context(
        self,
        db: AsyncSession,
        faculty_credential_id: UUID,
    ) -> tuple[FacultyCredentials, AppointmentLetter]:
        row = (
            await db.execute(
                select(FacultyCredentials, AppointmentLetter)
                .join(AppointmentLetter, AppointmentLetter.id == FacultyCredentials.appointment_letter_id)
                .where(FacultyCredentials.id == faculty_credential_id)
            )
        ).first()
        if not row:
            self._raise_error(404, "NOT_FOUND", "Faculty credential not found")
        return row

    async def _assert_principal_scope(self, current_user: User, institution_id: int) -> None:
        if current_user.role == RoleEnum.PRINCIPAL and current_user.institution_id != institution_id:
            self._raise_error(403, "UNAUTHORIZED_ACCESS", "You do not have access to this institution's data")

    async def _ensure_generation_gates(
        self,
        db: AsyncSession,
        faculty_credential_id: UUID,
        period_start: date,
        period_end: date,
        generated_by: int,
        academic_year: str,
        allow_rejected_regeneration: bool = True,
    ) -> tuple[FacultyCredentials, AppointmentLetter, list[LectureLog], Optional[CHBBill]]:
        credential, appointment = await self._get_faculty_context(db, faculty_credential_id)

        # Gate 1
        if not credential.is_active:
            self._raise_error(
                403,
                "FACULTY_CREDENTIALS_INACTIVE",
                "Faculty credentials are inactive for billing",
            )

        # Gate 2
        high_anomaly_count = int(
            (
                await db.execute(
                    select(func.count(AttendanceAnomaly.id))
                    .outerjoin(LectureLog, LectureLog.id == AttendanceAnomaly.lecture_log_id)
                    .outerjoin(DailyAttendanceSummary, DailyAttendanceSummary.id == AttendanceAnomaly.summary_id)
                    .where(
                        AttendanceAnomaly.faculty_credential_id == faculty_credential_id,
                        AttendanceAnomaly.severity == AnomalySeverity.HIGH.value,
                        AttendanceAnomaly.is_acknowledged.is_(False),
                        or_(
                            and_(
                                LectureLog.id.is_not(None),
                                LectureLog.lecture_date >= period_start,
                                LectureLog.lecture_date <= period_end,
                            ),
                            and_(
                                DailyAttendanceSummary.id.is_not(None),
                                DailyAttendanceSummary.attendance_date >= period_start,
                                DailyAttendanceSummary.attendance_date <= period_end,
                            ),
                        ),
                    )
                )
            ).scalar_one()
            or 0
        )
        if high_anomaly_count > 0:
            self._raise_error(
                403,
                "ANOMALY_UNACKNOWLEDGED",
                f"Resolve {high_anomaly_count} unacknowledged HIGH anomalies before generating bill",
            )

        # Gate 3
        unverified_count = int(
            (
                await db.execute(
                    select(func.count(LectureLog.id)).where(
                        LectureLog.faculty_credential_id == faculty_credential_id,
                        LectureLog.academic_year == academic_year,
                        LectureLog.lecture_date >= period_start,
                        LectureLog.lecture_date <= period_end,
                        LectureLog.log_status.in_([LectureLogStatus.DRAFT.value, LectureLogStatus.SUBMITTED.value]),
                    )
                )
            ).scalar_one()
            or 0
        )
        if unverified_count > 0:
            self._raise_error(
                400,
                "UNVERIFIED_LOGS_EXIST",
                f"Faculty has {unverified_count} unverified logs in the billing period",
            )

        existing_bill = (
            await db.execute(
                select(CHBBill).where(
                    CHBBill.faculty_credential_id == faculty_credential_id,
                    CHBBill.period_start == period_start,
                    CHBBill.period_end == period_end,
                )
            )
        ).scalars().first()

        # Gate 4
        if existing_bill and self._enum_value(existing_bill.bill_status) != BillStatus.REJECTED.value:
            self._raise_error(409, "BILL_ALREADY_EXISTS", "Bill already exists for this period")

        if (
            existing_bill
            and self._enum_value(existing_bill.bill_status) == BillStatus.REJECTED.value
            and allow_rejected_regeneration
        ):
            await db.execute(delete(BillLineItem).where(BillLineItem.bill_id == existing_bill.id))
            await db.execute(delete(BillApproval).where(BillApproval.bill_id == existing_bill.id))
            await db.execute(delete(BillAudit).where(BillAudit.bill_id == existing_bill.id))
            await db.execute(delete(CHBBill).where(CHBBill.id == existing_bill.id))
            await self._write_audit_log(
                db,
                "CHBBill",
                self._entity_id_from_uuid(existing_bill.id),
                "DELETE_REJECTED_FOR_REGEN",
                generated_by,
                old_value={"bill_number": existing_bill.bill_number, "status": self._enum_value(existing_bill.bill_status)},
                new_value={"reason": "auto-regenerate path from Gate 4"},
            )

        verified_logs = (
            await db.execute(
                select(LectureLog).where(
                    LectureLog.faculty_credential_id == faculty_credential_id,
                    LectureLog.academic_year == academic_year,
                    LectureLog.lecture_date >= period_start,
                    LectureLog.lecture_date <= period_end,
                    LectureLog.log_status == LectureLogStatus.VERIFIED.value,
                )
            )
        ).scalars().all()

        normalized_designation = self._normalize_designation(appointment.designation)
        lecture_types_present = {self._enum_value(row.lecture_type) for row in verified_logs}
        rate_map = await self._fetch_rate_map(
            db=db,
            institution_id=credential.institution_id,
            academic_year=academic_year,
            designation=normalized_designation,
            lecture_types=lecture_types_present,
        )

        # Gate 5
        missing_types = sorted(list(lecture_types_present.difference({item[1] for item in rate_map.keys()})))
        if missing_types:
            self._raise_error(
                400,
                "RATE_NOT_FOUND",
                f"Missing active rate for designation={normalized_designation}, lecture_types={','.join(missing_types)}",
            )

        return credential, appointment, verified_logs, existing_bill

    async def _fetch_rate_map(
        self,
        db: AsyncSession,
        institution_id: int,
        academic_year: str,
        designation: str,
        lecture_types: set[str],
    ) -> dict[tuple[str, str], Decimal]:
        if not lecture_types:
            return {}
        
        # Convert string designation to enum for comparison
        try:
            designation_enum = CHBDesignation[designation]
        except KeyError:
            # If designation doesn't match enum, return empty map (will trigger error later)
            return {}
        
        # Convert lecture type strings to enums
        lecture_type_enums = []
        for lt in lecture_types:
            try:
                lecture_type_enums.append(RateLectureType[lt])
            except KeyError:
                pass  # Skip invalid lecture types
        
        if not lecture_type_enums:
            return {}
        
        rows = (
            await db.execute(
                select(RateMaster)
                .where(
                    RateMaster.institution_id == institution_id,
                    RateMaster.academic_year == academic_year,
                    RateMaster.designation == designation_enum,
                    RateMaster.lecture_type.in_(lecture_type_enums),
                    RateMaster.is_active.is_(True),
                    or_(RateMaster.effective_to.is_(None), RateMaster.effective_to >= date.today()),
                )
                .order_by(RateMaster.effective_from.desc())
            )
        ).scalars().all()

        rate_map: dict[tuple[str, str], Decimal] = {}
        for row in rows:
            key = (self._enum_value(row.designation), self._enum_value(row.lecture_type))
            if key not in rate_map:
                rate_map[key] = Decimal(row.rate_per_lecture)
        return rate_map

    async def _generate_bill_number(
        self,
        db: AsyncSession,
        institution_id: int,
        period_start: date,
    ) -> str:
        """Generate an institution-scoped, month-scoped bill number atomically."""
        institution = (
            await db.execute(
                select(Institution).where(Institution.id == institution_id).with_for_update()
            )
        ).scalars().first()
        if not institution:
            self._raise_error(404, "NOT_FOUND", "Institution not found")

        month_token = period_start.strftime("%Y-%m")
        prefix = f"CHB/{month_token}/{institution.code}/"
        count = int(
            (
                await db.execute(
                    select(func.count(CHBBill.id)).where(
                        CHBBill.institution_id == institution_id,
                        CHBBill.bill_number.like(f"{prefix}%"),
                    )
                )
            ).scalar_one()
            or 0
        )
        seq = count + 1
        return f"{prefix}{seq:04d}"

    async def _build_bill_response(
        self,
        db: AsyncSession,
        bill: CHBBill,
        include_anomalies: bool = False,
    ) -> dict[str, Any]:
        line_items = (
            await db.execute(
                select(BillLineItem).where(BillLineItem.bill_id == bill.id).order_by(BillLineItem.lecture_date.asc(), BillLineItem.slot_number.asc())
            )
        ).scalars().all()
        approvals = (
            await db.execute(
                select(BillApproval).where(BillApproval.bill_id == bill.id).order_by(BillApproval.actioned_at.asc())
            )
        ).scalars().all()

        anomaly_flags: list[dict[str, Any]] = []
        if include_anomalies:
            anomalies = (
                await db.execute(
                    select(AttendanceAnomaly)
                    .outerjoin(LectureLog, LectureLog.id == AttendanceAnomaly.lecture_log_id)
                    .outerjoin(DailyAttendanceSummary, DailyAttendanceSummary.id == AttendanceAnomaly.summary_id)
                    .where(
                        AttendanceAnomaly.faculty_credential_id == bill.faculty_credential_id,
                        or_(
                            and_(
                                LectureLog.id.is_not(None),
                                LectureLog.lecture_date >= bill.period_start,
                                LectureLog.lecture_date <= bill.period_end,
                            ),
                            and_(
                                DailyAttendanceSummary.id.is_not(None),
                                DailyAttendanceSummary.attendance_date >= bill.period_start,
                                DailyAttendanceSummary.attendance_date <= bill.period_end,
                            ),
                        ),
                    )
                    .order_by(AttendanceAnomaly.created_at.desc())
                )
            ).scalars().all()
            anomaly_flags = [
                {
                    "id": row.id,
                    "anomaly_type": row.anomaly_type,
                    "severity": self._enum_value(row.severity),
                    "description": row.description,
                    "is_acknowledged": row.is_acknowledged,
                    "created_at": row.created_at,
                }
                for row in anomalies
            ]

        payload = CHBBillResponse(
            id=bill.id,
            bill_number=bill.bill_number,
            faculty_credential_id=bill.faculty_credential_id,
            institution_id=bill.institution_id,
            course_id=bill.course_id,
            academic_year=bill.academic_year,
            period_start=bill.period_start,
            period_end=bill.period_end,
            designation=bill.designation,
            total_theory_lectures=bill.total_theory_lectures,
            total_lab_lectures=bill.total_lab_lectures,
            total_tutorial_lectures=bill.total_tutorial_lectures,
            total_extra_lectures=bill.total_extra_lectures,
            total_substitute_lectures=bill.total_substitute_lectures,
            total_billable_lectures=bill.total_billable_lectures,
            gross_amount=Decimal(bill.gross_amount),
            deductions=Decimal(bill.deductions),
            net_amount=Decimal(bill.net_amount),
            bill_status=self._enum_value(bill.bill_status),
            current_approver_role=self._enum_value(bill.current_approver_role) if bill.current_approver_role else None,
            rejection_stage=bill.rejection_stage,
            rejection_reason=bill.rejection_reason,
            generated_by=bill.generated_by,
            generated_at=bill.generated_at,
            submitted_at=bill.submitted_at,
            treasury_processed_at=bill.treasury_processed_at,
            is_locked=bill.is_locked,
            created_at=bill.created_at,
            updated_at=bill.updated_at,
            line_items=[BillLineItemResponse.model_validate(row, from_attributes=True) for row in line_items],
            approval_chain=[
                {
                    "approver_role": self._enum_value(row.approver_role),
                    "action": self._enum_value(row.action),
                    "remarks": row.remarks,
                    "actioned_at": row.actioned_at,
                }
                for row in approvals
            ],
            anomaly_flags=anomaly_flags,
        )
        return payload.model_dump()

    async def _create_bill_from_logs(
        self,
        db: AsyncSession,
        credential: FacultyCredentials,
        appointment: AppointmentLetter,
        verified_logs: list[LectureLog],
        period_start: date,
        period_end: date,
        generated_by: int,
        academic_year: str,
        retained_bill_number: Optional[str] = None,
    ) -> CHBBill:
        rate_map = await self._fetch_rate_map(
            db,
            institution_id=credential.institution_id,
            academic_year=academic_year,
            designation=self._normalize_designation(appointment.designation),
            lecture_types={self._enum_value(row.lecture_type) for row in verified_logs},
        )
        try:
            output = bill_calculator.calculate_bill(
                BillCalculationInput(
                    faculty_credential_id=credential.id,
                    designation=self._normalize_designation(appointment.designation),
                    period_start=period_start,
                    period_end=period_end,
                    verified_logs=[LectureLogInput.model_validate(row, from_attributes=True) for row in verified_logs],
                    rate_map=rate_map,
                    max_daily_lectures=settings.MAX_DAILY_LECTURES,
                )
            )
        except BillCalculationError as exc:
            self._raise_error(400, exc.code, exc.message)

        bill_number = retained_bill_number or await self._generate_bill_number(db, credential.institution_id, period_start)
        deductions = Decimal("0.00")
        net_amount = output.gross_amount - deductions

        bill = CHBBill(
            bill_number=bill_number,
            faculty_credential_id=credential.id,
            institution_id=credential.institution_id,
            course_id=appointment.course_id,
            academic_year=academic_year,
            period_start=period_start,
            period_end=period_end,
            designation=self._normalize_designation(appointment.designation),
            total_theory_lectures=output.total_theory_lectures,
            total_lab_lectures=output.total_lab_lectures,
            total_tutorial_lectures=output.total_tutorial_lectures,
            total_extra_lectures=output.total_extra_lectures,
            total_substitute_lectures=output.total_substitute_lectures,
            total_billable_lectures=output.total_billable_lectures,
            gross_amount=output.gross_amount,
            deductions=deductions,
            net_amount=net_amount,
            bill_status=BillStatus.DRAFT.value,
            current_approver_role=None,
            generated_by=generated_by,
            generated_at=datetime.utcnow(),
            is_locked=False,
        )
        db.add(bill)
        await db.flush()

        await db.execute(
            update(DailyAttendanceSummary)
            .where(
                DailyAttendanceSummary.faculty_credential_id == credential.id,
                DailyAttendanceSummary.attendance_date >= period_start,
                DailyAttendanceSummary.attendance_date <= period_end,
            )
            .values(
                is_locked=True,
                lock_reason=f"Bill generated: {bill_number}",
                updated_at=datetime.utcnow(),
            )
        )
        # STEP 9 GATE: Bill is now locked. Payment disbursement in Step 9
        #              reads bills where bill_status = TREASURY_PROCESSED

        for item in output.line_items:
            db.add(
                BillLineItem(
                    bill_id=bill.id,
                    lecture_log_id=item.lecture_log_id,
                    lecture_date=item.lecture_date,
                    slot_number=item.slot_number,
                    subject_name=item.subject_name,
                    lecture_type=item.lecture_type,
                    class_name=item.class_name,
                    rate_per_lecture=item.rate_per_lecture,
                    amount=item.amount,
                    is_extra=item.is_extra,
                    is_substitute=item.is_substitute,
                )
            )

        await self._write_bill_audit(
            db,
            bill_id=bill.id,
            action=BillAuditAction.CREATED,
            performed_by=generated_by,
            old_status=None,
            new_status=BillStatus.DRAFT.value,
        )
        await self._write_audit_log(
            db,
            "CHBBill",
            self._entity_id_from_uuid(bill.id),
            "CREATE",
            generated_by,
            new_value={
                "bill_number": bill.bill_number,
                "status": BillStatus.DRAFT.value,
                "total_billable_lectures": bill.total_billable_lectures,
                "gross_amount": str(bill.gross_amount),
                "net_amount": str(bill.net_amount),
            },
        )
        return bill

    async def generate_bill(
        self,
        faculty_credential_id: UUID,
        period_start: date,
        period_end: date,
        generated_by: int,
        db: AsyncSession,
    ) -> CHBBill:
        """
        Generate a draft CHB bill for one faculty and billing period.

        Applies all pre-generation gates, snapshots rates into line-items, and locks daily summaries.
        """
        actor_id = generated_by
        credential, appointment = await self._get_faculty_context(db, faculty_credential_id)
        academic_year = appointment.academic_year
        credential, appointment, verified_logs, _ = await self._ensure_generation_gates(
            db=db,
            faculty_credential_id=faculty_credential_id,
            period_start=period_start,
            period_end=period_end,
            generated_by=actor_id,
            academic_year=academic_year,
            allow_rejected_regeneration=True,
        )
        bill = await self._create_bill_from_logs(
            db=db,
            credential=credential,
            appointment=appointment,
            verified_logs=verified_logs,
            period_start=period_start,
            period_end=period_end,
            generated_by=actor_id,
            academic_year=academic_year,
        )
        await db.commit()
        await db.refresh(bill)
        return bill

    async def process_bill_approval(
        self,
        bill_id: UUID,
        approver_id: int,
        approver_role: RoleEnum,
        action: Literal["APPROVE", "REJECT"],
        remarks: Optional[str],
        db: AsyncSession,
    ) -> CHBBill:
        """
        Process one approval-chain action and advance/reject the bill state.

        Only the currently expected approver role can act, and treasury approval finalizes/locks the bill.
        """
        bill = (await db.execute(select(CHBBill).where(CHBBill.id == bill_id))).scalars().first()
        if not bill:
            self._raise_error(404, "NOT_FOUND", "Bill not found")
        if bill.is_locked or self._enum_value(bill.bill_status) == BillStatus.TREASURY_PROCESSED.value:
            self._raise_error(403, "BILL_ALREADY_PROCESSED", "This bill is already treasury-processed")

        expected_role = self._enum_value(bill.current_approver_role) if bill.current_approver_role else None
        if expected_role != approver_role.value:
            self._raise_error(
                403,
                "UNAUTHORIZED_APPROVER",
                f"This bill is awaiting approval from {expected_role}",
            )

        if action == "REJECT" and (not remarks or not remarks.strip()):
            self._raise_error(400, "REJECTION_REASON_REQUIRED", "Remarks are required when rejecting a bill")

        old_status = self._enum_value(bill.bill_status)
        actor_id = approver_id

        if action == "REJECT":
            bill.bill_status = BillStatus.REJECTED.value
            bill.rejection_stage = approver_role.value
            bill.rejection_reason = remarks.strip() if remarks else None
            bill.current_approver_role = None

            db.add(
                BillApproval(
                    bill_id=bill.id,
                    approver_role=approver_role.value,
                    approver_id=actor_id,
                    action=BillApprovalAction.REJECTED.value,
                    remarks=bill.rejection_reason,
                    actioned_at=datetime.utcnow(),
                )
            )
            await self._write_bill_audit(
                db,
                bill_id=bill.id,
                action=BillAuditAction.REJECTED,
                performed_by=actor_id,
                old_status=old_status,
                new_status=BillStatus.REJECTED.value,
                remarks=bill.rejection_reason,
            )
            await self._write_audit_log(
                db,
                "CHBBill",
                self._entity_id_from_uuid(bill.id),
                "REJECT",
                actor_id,
                old_value={"bill_status": old_status},
                new_value={
                    "bill_status": BillStatus.REJECTED.value,
                    "rejection_stage": bill.rejection_stage,
                    "rejection_reason": bill.rejection_reason,
                },
            )
            return bill

        if approver_role == RoleEnum.PRINCIPAL:
            bill.bill_status = BillStatus.PRINCIPAL_APPROVED.value
            bill.current_approver_role = BillApproverRole.RO.value
            audit_action = BillAuditAction.APPROVED
        elif approver_role == RoleEnum.RO:
            bill.bill_status = BillStatus.RO_APPROVED.value
            bill.current_approver_role = BillApproverRole.TREASURY.value
            audit_action = BillAuditAction.APPROVED
        elif approver_role == RoleEnum.DIRECTORATE:
            bill.bill_status = BillStatus.DIRECTORATE_APPROVED.value
            bill.current_approver_role = BillApproverRole.TREASURY.value
            audit_action = BillAuditAction.APPROVED
        elif approver_role == RoleEnum.TREASURY:
            bill.bill_status = BillStatus.TREASURY_PROCESSED.value
            # STEP 9 TRIGGER
            # Payment module will pick this bill for disbursement
            bill.current_approver_role = None
            bill.treasury_processed_at = datetime.utcnow()
            bill.is_locked = True
            # STEP 9 GATE: Treasury-processed bills feed direct deposit in Step 9
            #              treasury_processed_at is the trigger timestamp
            audit_action = BillAuditAction.TREASURY_PROCESSED
        else:
            self._raise_error(403, "UNAUTHORIZED_APPROVER", "Unsupported approver role for bill approval")

        db.add(
            BillApproval(
                bill_id=bill.id,
                approver_role=approver_role.value,
                approver_id=actor_id,
                action=BillApprovalAction.APPROVED.value,
                remarks=remarks,
                actioned_at=datetime.utcnow(),
            )
        )
        await self._write_bill_audit(
            db,
            bill_id=bill.id,
            action=audit_action,
            performed_by=actor_id,
            old_status=old_status,
            new_status=self._enum_value(bill.bill_status),
            remarks=remarks,
        )
        await self._write_audit_log(
            db,
            "CHBBill",
            self._entity_id_from_uuid(bill.id),
            "APPROVE",
            actor_id,
            old_value={"bill_status": old_status},
            new_value={
                "bill_status": self._enum_value(bill.bill_status),
                "current_approver_role": self._enum_value(bill.current_approver_role)
                if bill.current_approver_role
                else None,
            },
        )
        return bill

    async def bulk_upsert_rates(self, db: AsyncSession, current_user: User, req: Any) -> list[dict[str, Any]]:
        """Create/update rate master rows in bulk for one institution and academic year."""
        await self._assert_principal_scope(current_user, req.institution_id)
        payload: list[dict[str, Any]] = []
        for item in req.rates:
            existing = (
                await db.execute(
                    select(RateMaster).where(
                        RateMaster.institution_id == req.institution_id,
                        RateMaster.academic_year == req.academic_year,
                        RateMaster.designation == item.designation,
                        RateMaster.lecture_type == item.lecture_type,
                        RateMaster.effective_from == item.effective_from,
                    )
                )
            ).scalars().first()

            if existing:
                old_values = {
                    "rate_per_lecture": str(existing.rate_per_lecture),
                    "effective_to": str(existing.effective_to) if existing.effective_to else None,
                    "is_active": existing.is_active,
                }
                existing.rate_per_lecture = item.rate_per_lecture
                existing.effective_to = item.effective_to
                existing.is_active = item.is_active
                row = existing
                action = "UPDATE"
                await self._write_audit_log(
                    db,
                    "RateMaster",
                    self._entity_id_from_uuid(existing.id),
                    action,
                    current_user.id,
                    old_value=old_values,
                    new_value={
                        "rate_per_lecture": str(existing.rate_per_lecture),
                        "effective_to": str(existing.effective_to) if existing.effective_to else None,
                        "is_active": existing.is_active,
                    },
                )
            else:
                row = RateMaster(
                    institution_id=req.institution_id,
                    academic_year=req.academic_year,
                    designation=item.designation,
                    lecture_type=item.lecture_type,
                    rate_per_lecture=item.rate_per_lecture,
                    effective_from=item.effective_from,
                    effective_to=item.effective_to,
                    is_active=item.is_active,
                    created_by=current_user.id,
                )
                db.add(row)
                await db.flush()
                action = "CREATE"
                await self._write_audit_log(
                    db,
                    "RateMaster",
                    self._entity_id_from_uuid(row.id),
                    action,
                    current_user.id,
                    new_value={
                        "designation": row.designation,
                        "lecture_type": row.lecture_type,
                        "rate_per_lecture": str(row.rate_per_lecture),
                    },
                )
            payload.append(
                {
                    "id": row.id,
                    "institution_id": row.institution_id,
                    "academic_year": row.academic_year,
                    "designation": self._enum_value(row.designation),
                    "lecture_type": self._enum_value(row.lecture_type),
                    "rate_per_lecture": row.rate_per_lecture,
                    "effective_from": row.effective_from,
                    "effective_to": row.effective_to,
                    "is_active": row.is_active,
                    "created_by": row.created_by,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }
            )
        await db.commit()
        return payload

    async def get_rates(
        self,
        db: AsyncSession,
        current_user: User,
        institution_id: int,
        academic_year: str,
        designation: Optional[str],
    ) -> dict[str, list[dict[str, Any]]]:
        """Get active rate master entries grouped by designation."""
        target_institution_id = institution_id
        if current_user.role == RoleEnum.PRINCIPAL:
            target_institution_id = current_user.institution_id
        if target_institution_id is None:
            self._raise_error(400, "HTTP_ERROR", "institution_id is required")

        stmt = select(RateMaster).where(
            RateMaster.institution_id == target_institution_id,
            RateMaster.academic_year == academic_year,
            RateMaster.is_active.is_(True),
        )
        if designation:
            stmt = stmt.where(RateMaster.designation == designation)
        rows = (
            await db.execute(stmt.order_by(RateMaster.designation.asc(), RateMaster.lecture_type.asc(), RateMaster.effective_from.desc()))
        ).scalars().all()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            key = self._enum_value(row.designation)
            grouped.setdefault(key, []).append(
                {
                    "id": row.id,
                    "institution_id": row.institution_id,
                    "academic_year": row.academic_year,
                    "designation": self._enum_value(row.designation),
                    "lecture_type": self._enum_value(row.lecture_type),
                    "rate_per_lecture": row.rate_per_lecture,
                    "effective_from": row.effective_from,
                    "effective_to": row.effective_to,
                    "is_active": row.is_active,
                    "created_by": row.created_by,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }
            )
        return grouped

    async def update_rate(self, db: AsyncSession, current_user: User, rate_id: UUID, req: Any) -> dict[str, Any]:
        """Update a rate row unless bills already reference its snapshot value."""
        rate = (await db.execute(select(RateMaster).where(RateMaster.id == rate_id))).scalars().first()
        if not rate:
            self._raise_error(404, "NOT_FOUND", "Rate not found")

        in_use = int(
            (
                await db.execute(
                    select(func.count(BillLineItem.id))
                    .join(CHBBill, CHBBill.id == BillLineItem.bill_id)
                    .where(
                        CHBBill.institution_id == rate.institution_id,
                        CHBBill.academic_year == rate.academic_year,
                        CHBBill.designation == self._enum_value(rate.designation),
                        BillLineItem.lecture_type == self._enum_value(rate.lecture_type),
                        BillLineItem.rate_per_lecture == rate.rate_per_lecture,
                    )
                )
            ).scalar_one()
            or 0
        )
        if in_use > 0:
            self._raise_error(403, "RATE_IN_USE", "Cannot edit a rate already used in generated bills")

        old_values = {
            "rate_per_lecture": str(rate.rate_per_lecture),
            "effective_to": str(rate.effective_to) if rate.effective_to else None,
            "is_active": rate.is_active,
        }
        if req.rate_per_lecture is not None:
            rate.rate_per_lecture = req.rate_per_lecture
        if req.effective_to is not None:
            rate.effective_to = req.effective_to
        if req.is_active is not None:
            rate.is_active = req.is_active

        await self._write_audit_log(
            db,
            "RateMaster",
            self._entity_id_from_uuid(rate.id),
            "UPDATE",
            current_user.id,
            old_value=old_values,
            new_value={
                "rate_per_lecture": str(rate.rate_per_lecture),
                "effective_to": str(rate.effective_to) if rate.effective_to else None,
                "is_active": rate.is_active,
            },
        )
        await db.commit()
        await db.refresh(rate)
        return {
            "id": rate.id,
            "institution_id": rate.institution_id,
            "academic_year": rate.academic_year,
            "designation": self._enum_value(rate.designation),
            "lecture_type": self._enum_value(rate.lecture_type),
            "rate_per_lecture": rate.rate_per_lecture,
            "effective_from": rate.effective_from,
            "effective_to": rate.effective_to,
            "is_active": rate.is_active,
            "created_by": rate.created_by,
            "created_at": rate.created_at,
            "updated_at": rate.updated_at,
        }

    async def generate_bill_endpoint(self, db: AsyncSession, current_user: User, req: Any) -> dict[str, Any]:
        """Endpoint wrapper for one-bill generation with request-level role scoping."""
        credential, appointment = await self._get_faculty_context(db, req.faculty_credential_id)
        await self._assert_principal_scope(current_user, credential.institution_id)
        if appointment.academic_year != req.academic_year:
            self._raise_error(
                400,
                "HTTP_ERROR",
                f"Academic year mismatch. Faculty appointment is in {appointment.academic_year}",
            )
        bill = await self.generate_bill(
            faculty_credential_id=req.faculty_credential_id,
            period_start=req.period_start,
            period_end=req.period_end,
            generated_by=current_user.id,
            db=db,
        )
        return await self._build_bill_response(db, bill)

    async def generate_bulk_bills(self, db: AsyncSession, current_user: User, req: Any) -> dict[str, Any]:
        """Generate bills for all active faculty in an institution while skipping failing rows."""
        if current_user.role != RoleEnum.ADMIN:
            self._raise_error(403, "UNAUTHORIZED_ACCESS", "Only ADMIN can run bulk bill generation")

        rows = (
            await db.execute(
                select(FacultyCredentials.id)
                .join(AppointmentLetter, AppointmentLetter.id == FacultyCredentials.appointment_letter_id)
                .where(
                    FacultyCredentials.institution_id == req.institution_id,
                    FacultyCredentials.is_active.is_(True),
                    AppointmentLetter.academic_year == req.academic_year,
                )
            )
        ).scalars().all()

        success_count = 0
        skipped: list[dict[str, Any]] = []
        for faculty_credential_id in rows:
            try:
                await self.generate_bill(
                    faculty_credential_id=faculty_credential_id,
                    period_start=req.period_start,
                    period_end=req.period_end,
                    generated_by=current_user.id,
                    db=db,
                )
                success_count += 1
            except HTTPException as exc:
                await db.rollback()
                detail = exc.detail if isinstance(exc.detail, dict) else {}
                skipped.append(
                    {
                        "faculty_credential_id": faculty_credential_id,
                        "reason": detail.get("code", "HTTP_ERROR"),
                    }
                )
        return {"success_count": success_count, "skipped": skipped}

    async def submit_bill(self, db: AsyncSession, current_user: User, bill_id: UUID) -> dict[str, Any]:
        """Submit a draft bill into the fixed approval chain."""
        bill = (await db.execute(select(CHBBill).where(CHBBill.id == bill_id))).scalars().first()
        if not bill:
            self._raise_error(404, "NOT_FOUND", "Bill not found")
        await self._assert_principal_scope(current_user, bill.institution_id)
        if self._enum_value(bill.bill_status) != BillStatus.DRAFT.value:
            self._raise_error(403, "BILL_NOT_SUBMITTABLE", "Only DRAFT bills can be submitted")

        old_status = self._enum_value(bill.bill_status)
        bill.bill_status = BillStatus.SUBMITTED.value
        bill.current_approver_role = BillApproverRole.PRINCIPAL.value
        bill.submitted_at = datetime.utcnow()
        await self._write_bill_audit(
            db,
            bill_id=bill.id,
            action=BillAuditAction.SUBMITTED,
            performed_by=current_user.id,
            old_status=old_status,
            new_status=BillStatus.SUBMITTED.value,
        )
        await self._write_audit_log(
            db,
            "CHBBill",
            self._entity_id_from_uuid(bill.id),
            "SUBMIT",
            current_user.id,
            old_value={"bill_status": old_status},
            new_value={"bill_status": BillStatus.SUBMITTED.value, "current_approver_role": BillApproverRole.PRINCIPAL.value},
        )
        await db.commit()
        await db.refresh(bill)
        return {"bill_id": bill.id, "bill_status": self._enum_value(bill.bill_status)}

    async def approve_bill_endpoint(
        self,
        db: AsyncSession,
        current_user: User,
        bill_id: UUID,
        req: BillApprovalRequest,
    ) -> dict[str, Any]:
        """Approve or reject one bill at the caller's role stage."""
        if current_user.role not in {RoleEnum.PRINCIPAL, RoleEnum.RO, RoleEnum.DIRECTORATE, RoleEnum.TREASURY}:
            self._raise_error(403, "UNAUTHORIZED_APPROVER", "Role cannot approve/reject bills")
        bill = await self.process_bill_approval(
            bill_id=bill_id,
            approver_id=current_user.id,
            approver_role=current_user.role,
            action=req.action.value,
            remarks=req.remarks,
            db=db,
        )
        await db.commit()
        await db.refresh(bill)
        return await self._build_bill_response(db, bill)

    async def get_bill_approvals(self, db: AsyncSession, current_user: User, bill_id: UUID) -> dict[str, Any]:
        """Return full bill approval-chain history with current pending stage."""
        bill = (await db.execute(select(CHBBill).where(CHBBill.id == bill_id))).scalars().first()
        if not bill:
            self._raise_error(404, "NOT_FOUND", "Bill not found")
        await self._assert_read_scope(db, current_user, bill)

        rows = (
            await db.execute(
                select(BillApproval).where(BillApproval.bill_id == bill_id).order_by(BillApproval.actioned_at.asc())
            )
        ).scalars().all()
        return {
            "bill_id": bill_id,
            "current_approver_role": self._enum_value(bill.current_approver_role) if bill.current_approver_role else None,
            "history": [
                {
                    "approver_role": self._enum_value(row.approver_role),
                    "action": self._enum_value(row.action),
                    "remarks": row.remarks,
                    "actioned_at": row.actioned_at,
                }
                for row in rows
            ],
        }

    async def _assert_read_scope(self, db: AsyncSession, current_user: User, bill: CHBBill) -> None:
        if current_user.role == RoleEnum.ADMIN:
            return
        if current_user.role == RoleEnum.PRINCIPAL:
            await self._assert_principal_scope(current_user, bill.institution_id)
            return
        if current_user.role == RoleEnum.FACULTY:
            own_credential = (
                await db.execute(
                    select(FacultyCredentials.id).where(FacultyCredentials.user_id == current_user.id)
                )
            ).scalar_one_or_none()
            if not own_credential or own_credential != bill.faculty_credential_id:
                self._raise_error(403, "UNAUTHORIZED_ACCESS", "Faculty can view only their own bills")
            return
        if current_user.role in {RoleEnum.RO, RoleEnum.DIRECTORATE, RoleEnum.TREASURY}:
            return
        self._raise_error(403, "UNAUTHORIZED_ACCESS", "Role does not have access to bills")

    async def list_bills(
        self,
        db: AsyncSession,
        current_user: User,
        faculty_credential_id: Optional[UUID],
        institution_id: Optional[int],
        course_id: Optional[int],
        academic_year: Optional[str],
        period_start: Optional[date],
        period_end: Optional[date],
        bill_status: Optional[str],
        current_approver_role: Optional[str],
        skip: int = 0,
        limit: int = 10,
    ) -> tuple[list[dict[str, Any]], int]:
        """List bills with role-scoped filters and queue-scoped views for approval roles."""
        stmt = select(CHBBill, User.full_name.label("faculty_name")).outerjoin(
            FacultyCredentials, CHBBill.faculty_credential_id == FacultyCredentials.id
        ).outerjoin(
            User, FacultyCredentials.user_id == User.id
        )
        filters = []

        if faculty_credential_id:
            filters.append(CHBBill.faculty_credential_id == faculty_credential_id)
        if institution_id:
            filters.append(CHBBill.institution_id == institution_id)
        if course_id:
            filters.append(CHBBill.course_id == course_id)
        if academic_year:
            filters.append(CHBBill.academic_year == academic_year)
        if period_start:
            filters.append(CHBBill.period_start >= period_start)
        if period_end:
            filters.append(CHBBill.period_end <= period_end)
        if bill_status:
            filters.append(CHBBill.bill_status == bill_status)
        if current_approver_role:
            filters.append(CHBBill.current_approver_role == current_approver_role)

        if current_user.role == RoleEnum.FACULTY:
            own_credential_id = (
                await db.execute(select(FacultyCredentials.id).where(FacultyCredentials.user_id == current_user.id))
            ).scalar_one_or_none()
            if own_credential_id is None:
                return []
            filters.append(CHBBill.faculty_credential_id == own_credential_id)
        elif current_user.role == RoleEnum.PRINCIPAL:
            if current_user.institution_id is None:
                self._raise_error(403, "UNAUTHORIZED_ACCESS", "Principal is not mapped to an institution")
            filters.append(CHBBill.institution_id == current_user.institution_id)
        elif current_user.role in {RoleEnum.RO, RoleEnum.DIRECTORATE, RoleEnum.TREASURY}:
            filters.append(CHBBill.current_approver_role == current_user.role.value)

        from sqlalchemy import func
        count_stmt = select(func.count()).select_from(stmt.where(*filters).subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = stmt.where(*filters).order_by(CHBBill.created_at.desc())
        if limit > 0:
            stmt = stmt.offset(skip).limit(limit)

        rows = (await db.execute(stmt)).all()
        result_list = [
            {
                "id": row.CHBBill.id,
                "bill_number": row.CHBBill.bill_number,
                "faculty_credential_id": row.CHBBill.faculty_credential_id,
                "faculty_name": row.faculty_name,
                "institution_id": row.CHBBill.institution_id,
                "course_id": row.CHBBill.course_id,
                "academic_year": row.CHBBill.academic_year,
                "period_start": row.CHBBill.period_start,
                "period_end": row.CHBBill.period_end,
                "designation": row.CHBBill.designation,
                "total_theory_lectures": row.CHBBill.total_theory_lectures,
                "total_lab_lectures": row.CHBBill.total_lab_lectures,
                "total_tutorial_lectures": row.CHBBill.total_tutorial_lectures,
                "total_extra_lectures": row.CHBBill.total_extra_lectures,
                "total_substitute_lectures": row.CHBBill.total_substitute_lectures,
                "total_billable_lectures": row.CHBBill.total_billable_lectures,
                "gross_amount": row.CHBBill.gross_amount,
                "deductions": row.CHBBill.deductions,
                "net_amount": row.CHBBill.net_amount,
                "total_amount": row.CHBBill.net_amount,
                "bill_status": self._enum_value(row.CHBBill.bill_status),
                "current_approver_role": self._enum_value(row.CHBBill.current_approver_role) if row.CHBBill.current_approver_role else None,
                "rejection_stage": row.CHBBill.rejection_stage,
                "rejection_reason": row.CHBBill.rejection_reason,
                "generated_by": row.CHBBill.generated_by,
                "generated_at": row.CHBBill.generated_at,
                "submitted_at": row.CHBBill.submitted_at,
                "treasury_processed_at": row.CHBBill.treasury_processed_at,
                "is_locked": row.CHBBill.is_locked,
                "created_at": row.CHBBill.created_at,
                "updated_at": row.CHBBill.updated_at,
            }
            for row in rows
        ]
        return result_list, total
        return result_list, total

    async def get_bill_detail(self, db: AsyncSession, current_user: User, bill_id: UUID) -> dict[str, Any]:
        """Return full bill detail including line-items, approvals, and linked anomaly flags."""
        bill = (await db.execute(select(CHBBill).where(CHBBill.id == bill_id))).scalars().first()
        if not bill:
            self._raise_error(404, "NOT_FOUND", "Bill not found")
        await self._assert_read_scope(db, current_user, bill)
        return await self._build_bill_response(db, bill, include_anomalies=True)

    async def get_institution_summary(
        self,
        db: AsyncSession,
        current_user: User,
        institution_id: Optional[int],
        academic_year: Optional[str],
        month: Optional[int],
        bill_status: Optional[str],
    ) -> dict[str, Any]:
        """Return institution-level aggregate billing summary statistics."""
        target_institution_id = institution_id
        if current_user.role == RoleEnum.PRINCIPAL:
            target_institution_id = current_user.institution_id

        filters = []
        if target_institution_id is not None:
            filters.append(CHBBill.institution_id == target_institution_id)
        elif current_user.role not in {RoleEnum.ADMIN, RoleEnum.RO, RoleEnum.DIRECTORATE, RoleEnum.TREASURY}:
            self._raise_error(400, "HTTP_ERROR", "institution_id is required")

        if academic_year:
            filters.append(CHBBill.academic_year == academic_year)
        if month:
            filters.append(extract("month", CHBBill.period_start) == month)
        if bill_status:
            filters.append(CHBBill.bill_status == bill_status)

        total_bills_generated = int(
            (
                await db.execute(select(func.count(CHBBill.id)).where(*filters))
            ).scalar_one()
            or 0
        )
        totals = (
            await db.execute(
                select(
                    func.coalesce(func.sum(CHBBill.gross_amount), 0),
                    func.coalesce(func.sum(CHBBill.net_amount), 0),
                ).where(*filters)
            )
        ).first()
        total_gross_amount = Decimal(totals[0] or 0)
        total_net_amount = Decimal(totals[1] or 0)
        
        approved_totals = (
            await db.execute(
                select(func.coalesce(func.sum(CHBBill.net_amount), 0)).where(
                    *filters, 
                    CHBBill.bill_status == BillStatus.TREASURY_PROCESSED.value
                )
            )
        ).scalar_one()
        total_approved_amount = Decimal(approved_totals or 0)

        bills_pending_principal = int(
            (
                await db.execute(
                    select(func.count(CHBBill.id)).where(*filters, CHBBill.current_approver_role == BillApproverRole.PRINCIPAL.value)
                )
            ).scalar_one()
            or 0
        )
        bills_pending_ro = int(
            (
                await db.execute(
                    select(func.count(CHBBill.id)).where(*filters, CHBBill.current_approver_role == BillApproverRole.RO.value)
                )
            ).scalar_one()
            or 0
        )
        bills_pending_directorate = int(
            (
                await db.execute(
                    select(func.count(CHBBill.id)).where(*filters, CHBBill.current_approver_role == BillApproverRole.DIRECTORATE.value)
                )
            ).scalar_one()
            or 0
        )
        bills_pending_treasury = int(
            (
                await db.execute(
                    select(func.count(CHBBill.id)).where(*filters, CHBBill.current_approver_role == BillApproverRole.TREASURY.value)
                )
            ).scalar_one()
            or 0
        )
        
        draft_count = int(
            (
                await db.execute(select(func.count(CHBBill.id)).where(*filters, CHBBill.bill_status == 'DRAFT'))
            ).scalar_one()
            or 0
        )

        bills_rejected = int(
            (await db.execute(select(func.count(CHBBill.id)).where(*filters, CHBBill.bill_status == BillStatus.REJECTED.value))).scalar_one()
            or 0
        )
        bills_processed = int(
            (
                await db.execute(select(func.count(CHBBill.id)).where(*filters, CHBBill.bill_status == BillStatus.TREASURY_PROCESSED.value))
            ).scalar_one()
            or 0
        )

        return {
            "total_bills_generated": total_bills_generated,
            "total_gross_amount": total_gross_amount,
            "total_net_amount": total_net_amount,
            "total_approved_amount": total_approved_amount,
            "draft_count": draft_count,
            "bills_pending_principal": bills_pending_principal,
            "bills_pending_ro": bills_pending_ro,
            "bills_pending_directorate": bills_pending_directorate,
            "bills_pending_treasury": bills_pending_treasury,
            "bills_rejected": bills_rejected,
            "bills_processed": bills_processed,
        }

    async def regenerate_bill(self, db: AsyncSession, current_user: User, bill_id: UUID) -> dict[str, Any]:
        """Regenerate a REJECTED bill in place while retaining bill number."""
        bill = (await db.execute(select(CHBBill).where(CHBBill.id == bill_id))).scalars().first()
        if not bill:
            self._raise_error(404, "NOT_FOUND", "Bill not found")
        await self._assert_principal_scope(current_user, bill.institution_id)
        if self._enum_value(bill.bill_status) != BillStatus.REJECTED.value:
            self._raise_error(403, "BILL_NOT_REGENERABLE", "Only REJECTED bills can be regenerated")

        credential, appointment, verified_logs, _ = await self._ensure_generation_gates(
            db=db,
            faculty_credential_id=bill.faculty_credential_id,
            period_start=bill.period_start,
            period_end=bill.period_end,
            generated_by=current_user.id,
            academic_year=bill.academic_year,
            allow_rejected_regeneration=False,
        )

        await db.execute(delete(BillLineItem).where(BillLineItem.bill_id == bill.id))
        await db.execute(delete(BillApproval).where(BillApproval.bill_id == bill.id))

        rate_map = await self._fetch_rate_map(
            db=db,
            institution_id=credential.institution_id,
            academic_year=bill.academic_year,
            designation=self._normalize_designation(appointment.designation),
            lecture_types={self._enum_value(row.lecture_type) for row in verified_logs},
        )
        try:
            output = bill_calculator.calculate_bill(
                BillCalculationInput(
                    faculty_credential_id=bill.faculty_credential_id,
                    designation=self._normalize_designation(appointment.designation),
                    period_start=bill.period_start,
                    period_end=bill.period_end,
                    verified_logs=[LectureLogInput.model_validate(row, from_attributes=True) for row in verified_logs],
                    rate_map=rate_map,
                    max_daily_lectures=settings.MAX_DAILY_LECTURES,
                )
            )
        except BillCalculationError as exc:
            self._raise_error(400, exc.code, exc.message)

        old_status = self._enum_value(bill.bill_status)
        bill.designation = self._normalize_designation(appointment.designation)
        bill.total_theory_lectures = output.total_theory_lectures
        bill.total_lab_lectures = output.total_lab_lectures
        bill.total_tutorial_lectures = output.total_tutorial_lectures
        bill.total_extra_lectures = output.total_extra_lectures
        bill.total_substitute_lectures = output.total_substitute_lectures
        bill.total_billable_lectures = output.total_billable_lectures
        bill.gross_amount = output.gross_amount
        bill.deductions = Decimal("0.00")
        bill.net_amount = output.gross_amount
        bill.bill_status = BillStatus.DRAFT.value
        bill.current_approver_role = None
        bill.rejection_stage = None
        bill.rejection_reason = None
        bill.generated_by = current_user.id
        bill.generated_at = datetime.utcnow()
        bill.submitted_at = None
        bill.treasury_processed_at = None
        bill.is_locked = False

        await db.execute(
            update(DailyAttendanceSummary)
            .where(
                DailyAttendanceSummary.faculty_credential_id == bill.faculty_credential_id,
                DailyAttendanceSummary.attendance_date >= bill.period_start,
                DailyAttendanceSummary.attendance_date <= bill.period_end,
            )
            .values(
                is_locked=True,
                lock_reason=f"Bill generated: {bill.bill_number}",
                updated_at=datetime.utcnow(),
            )
        )

        for item in output.line_items:
            db.add(
                BillLineItem(
                    bill_id=bill.id,
                    lecture_log_id=item.lecture_log_id,
                    lecture_date=item.lecture_date,
                    slot_number=item.slot_number,
                    subject_name=item.subject_name,
                    lecture_type=item.lecture_type,
                    class_name=item.class_name,
                    rate_per_lecture=item.rate_per_lecture,
                    amount=item.amount,
                    is_extra=item.is_extra,
                    is_substitute=item.is_substitute,
                )
            )

        await self._write_bill_audit(
            db,
            bill_id=bill.id,
            action=BillAuditAction.REGENERATED,
            performed_by=current_user.id,
            old_status=old_status,
            new_status=BillStatus.DRAFT.value,
        )
        await self._write_audit_log(
            db,
            "CHBBill",
            self._entity_id_from_uuid(bill.id),
            "REGENERATE",
            current_user.id,
            old_value={"bill_status": old_status},
            new_value={"bill_status": BillStatus.DRAFT.value, "bill_number": bill.bill_number},
        )
        await db.commit()
        await db.refresh(bill)
        return await self._build_bill_response(db, bill, include_anomalies=True)
