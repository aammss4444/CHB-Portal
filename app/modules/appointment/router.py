from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import RoleChecker, get_current_user
from app.db.session import get_db
from app.models.user import RoleEnum, User
from app.modules.appointment.controller import AppointmentController
from app.modules.appointment.schemas import (
    AppointmentApproveRequest,
    AppointmentCancelRequest,
    AppointmentGenerateRequest,
    AppointmentRespondRequest,
    AppointmentUpdateRequest,
)


router = APIRouter(prefix="/appointments", tags=["Appointment Management (Step 6)"])
controller = AppointmentController()

principal_only = RoleChecker([RoleEnum.PRINCIPAL])
admin_only = RoleChecker([RoleEnum.ADMIN])
candidate_only = RoleChecker([RoleEnum.CANDIDATE])
admin_or_principal = RoleChecker([RoleEnum.ADMIN, RoleEnum.PRINCIPAL])
admin_principal_candidate = RoleChecker([RoleEnum.ADMIN, RoleEnum.PRINCIPAL, RoleEnum.CANDIDATE])


@router.post("/generate", dependencies=[Depends(principal_only)])
async def generate_appointment(
    req: AppointmentGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.generate(db, current_user, req)


@router.get("/{appointment_id}", dependencies=[Depends(admin_principal_candidate)])
async def get_appointment(
    appointment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.get(db, current_user, appointment_id)


@router.put("/{appointment_id}", dependencies=[Depends(principal_only)])
async def update_appointment(
    appointment_id: UUID,
    req: AppointmentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.update(db, current_user, appointment_id, req)


@router.post("/{appointment_id}/submit", dependencies=[Depends(principal_only)])
async def submit_appointment(
    appointment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.submit(db, current_user, appointment_id)


@router.post("/{appointment_id}/approve", dependencies=[Depends(admin_only)])
async def approve_appointment(
    appointment_id: UUID,
    req: AppointmentApproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.approve(db, current_user, appointment_id, req)


@router.post("/{appointment_id}/issue", dependencies=[Depends(admin_only)])
async def issue_appointment(
    appointment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.issue(db, current_user, appointment_id)


@router.post("/{appointment_id}/respond", dependencies=[Depends(candidate_only)])
async def respond_appointment(
    appointment_id: UUID,
    req: AppointmentRespondRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ip_address = request.client.host if request.client else None
    return await controller.respond(db, current_user, appointment_id, req, ip_address)


@router.post("/{appointment_id}/cancel", dependencies=[Depends(admin_only)])
async def cancel_appointment(
    appointment_id: UUID,
    req: AppointmentCancelRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.cancel(db, current_user, appointment_id, req)


@router.post("/{appointment_id}/credentials", dependencies=[Depends(admin_only)])
async def issue_appointment_credentials(
    appointment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.credentials(db, current_user, appointment_id)


@router.get("/institution/{institution_id}", dependencies=[Depends(admin_or_principal)])
async def list_appointments_by_institution(
    institution_id: int,
    academic_year: str | None = Query(None),
    status: str | None = Query(None),
    course_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.list_institution(
        db, current_user, institution_id, academic_year, status, course_id, page, size
    )
