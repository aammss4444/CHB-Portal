from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, HTTPException
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
candidate_only = RoleChecker([RoleEnum.CANDIDATE])
principal_or_candidate = RoleChecker([RoleEnum.PRINCIPAL, RoleEnum.CANDIDATE])

@router.get("/list", dependencies=[Depends(principal_only)])
async def list_principal_appointments(
    academic_year: str | None = Query(None),
    status: str | None = Query(None),
    course_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List appointments for the logged-in Principal's institute"""
    if not current_user.institution_id:
        raise HTTPException(status_code=403, detail="Principal not assigned to institution")
    return await controller.list_institution(
        db, current_user, current_user.institution_id, academic_year, status, course_id, page, size
    )

@router.get("/my/list", dependencies=[Depends(candidate_only)])
async def list_candidate_appointments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Candidate lists all received appointments"""
    return await controller.list_candidate(db, current_user)

@router.post("/generate", dependencies=[Depends(principal_only)])
async def generate_appointment(
    req: AppointmentGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate appointment letter by Principal (AI-assisted)"""
    return await controller.generate(db, current_user, req)

@router.get("/{appointment_id}", dependencies=[Depends(principal_or_candidate)])
async def get_appointment(
    appointment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """View appointment details (Principal or Candidate)"""
    return await controller.get(db, current_user, appointment_id)

@router.put("/{appointment_id}", dependencies=[Depends(principal_only)])
async def update_appointment(
    appointment_id: UUID,
    req: AppointmentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update draft appointment (Principal only)"""
    return await controller.update(db, current_user, appointment_id, req)

@router.delete("/{appointment_id}", dependencies=[Depends(principal_only)])
async def delete_appointment(
    appointment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Permanently delete an appointment letter (Principal only)"""
    return await controller.delete(db, current_user, appointment_id)

@router.post("/{appointment_id}/submit", dependencies=[Depends(principal_only)])
async def submit_appointment(
    appointment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit appointment directly to candidate (Principal only)"""
    return await controller.submit(db, current_user, appointment_id)

@router.post("/{appointment_id}/respond", dependencies=[Depends(candidate_only)])
async def respond_appointment(
    appointment_id: UUID,
    req: AppointmentRespondRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Candidate accepts or rejects the appointment"""
    ip_address = request.client.host if request.client else None
    return await controller.respond(db, current_user, appointment_id, req, ip_address)
