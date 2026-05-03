from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import RoleChecker, get_current_user
from app.db.session import get_db
from app.models.user import RoleEnum, User
from app.modules.attendance.controller import AttendanceController
from app.modules.attendance.schemas import (
    AnomalyAcknowledgeRequest,
    BulkSubmitRequest,
    CalendarBulkUpsertRequest,
    LectureLogCreateRequest,
    LectureLogSubmitRequest,
    LectureLogUpdateRequest,
    LectureLogVerifyRequest,
    TimetableSlotCreateRequest,
    TimetableSlotUpdateRequest,
)
from app.dependencies.pagination import PaginationParams

router = APIRouter(prefix="/attendance", tags=["Attendance & Work Log (Step 7)"])
controller = AttendanceController()

principal_only = RoleChecker([RoleEnum.PRINCIPAL])
admin_or_principal = RoleChecker([RoleEnum.ADMIN, RoleEnum.PRINCIPAL])
staff_or_faculty = RoleChecker([RoleEnum.ADMIN, RoleEnum.PRINCIPAL, RoleEnum.FACULTY])
faculty_only = RoleChecker([RoleEnum.FACULTY])


@router.post("/timetable", dependencies=[Depends(principal_only)])
async def create_timetable(
    req: TimetableSlotCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.create_timetable(db, current_user, req)


@router.get("/timetable/{faculty_credential_id}", dependencies=[Depends(staff_or_faculty)])
async def get_timetable(
    faculty_credential_id: UUID,
    academic_year: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.get_timetable(db, current_user, faculty_credential_id, academic_year)


@router.put("/timetable/{slot_id}", dependencies=[Depends(principal_only)])
async def update_timetable_slot(
    slot_id: UUID,
    req: TimetableSlotUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.update_timetable(db, current_user, slot_id, req)


@router.post("/calendar", dependencies=[Depends(admin_or_principal)])
async def upsert_calendar(
    req: CalendarBulkUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.upsert_calendar(db, current_user, req)


@router.get("/calendar", dependencies=[Depends(staff_or_faculty)])
async def get_calendar(
    institution_id: Optional[int] = Query(None),
    academic_year: str = Query(...),
    month: Optional[int] = Query(None, ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.get_calendar(db, current_user, institution_id, academic_year, month)


@router.get("/logs/summary", dependencies=[Depends(staff_or_faculty)])
async def get_monthly_summary(
    faculty_credential_id: Optional[UUID] = Query(None),
    academic_year: str = Query(...),
    month: int = Query(..., ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.get_monthly_summary(db, current_user, faculty_credential_id, academic_year, month)


@router.get("/logs", dependencies=[Depends(staff_or_faculty)])
async def list_logs(
    pagination: PaginationParams = Depends(),
    faculty_credential_id: Optional[UUID] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None),
    academic_year: Optional[str] = Query(None),
    log_status: Optional[str] = Query(None),
    course_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.list_logs(
        db, current_user, faculty_credential_id, month, year, academic_year, log_status, course_id, pagination.skip, pagination.limit
    )


@router.post("/logs", dependencies=[Depends(faculty_only)])
async def create_log(
    req: LectureLogCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.create_log(db, current_user, req, background_tasks)


@router.post("/logs/bulk-submit", dependencies=[Depends(faculty_only)])
async def bulk_submit_logs(
    req: BulkSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.bulk_submit(db, current_user, req)


@router.put("/logs/{log_id}", dependencies=[Depends(faculty_only)])
async def update_log(
    log_id: UUID,
    req: LectureLogUpdateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.update_log(db, current_user, log_id, req, background_tasks)


@router.post("/logs/{log_id}/submit", dependencies=[Depends(faculty_only)])
async def submit_log(
    log_id: UUID,
    req: LectureLogSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.submit_log(db, current_user, log_id)


@router.post("/logs/{log_id}/verify", dependencies=[Depends(principal_only)])
async def verify_log(
    log_id: UUID,
    req: LectureLogVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.verify_log(db, current_user, log_id, req)


@router.get("/anomalies", dependencies=[Depends(admin_or_principal)])
async def list_anomalies(
    pagination: PaginationParams = Depends(),
    faculty_credential_id: Optional[UUID] = Query(None),
    severity: Optional[str] = Query(None),
    is_acknowledged: Optional[bool] = Query(None),
    institution_id: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.list_anomalies(
        db, current_user, faculty_credential_id, severity, is_acknowledged, institution_id, month, year, pagination.skip, pagination.limit
    )


@router.post("/anomalies/{anomaly_id}/acknowledge", dependencies=[Depends(principal_only)])
async def acknowledge_anomaly(
    anomaly_id: UUID,
    req: AnomalyAcknowledgeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.acknowledge_anomaly(db, current_user, anomaly_id, req.remarks)

@router.post("/logs/{log_id}/ai-check", dependencies=[Depends(principal_only)])
async def ai_check_log(
    log_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.ai_check_log(db, current_user, log_id)

@router.get("/faculty/{faculty_credential_id}/ai-analysis", dependencies=[Depends(admin_or_principal)])
async def ai_analysis(
    faculty_credential_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.ai_analysis(db, current_user, faculty_credential_id)

@router.get("/ai-monitor", dependencies=[Depends(RoleChecker([RoleEnum.ADMIN]))])
async def ai_monitor(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.ai_monitor(db, current_user)

@router.post("/faculty/{faculty_credential_id}/ai-snapshot", dependencies=[Depends(admin_or_principal)])
async def ai_snapshot(
    faculty_credential_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.ai_snapshot(db, current_user, faculty_credential_id)
