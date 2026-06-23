from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.db.session import get_db
from app.core.security import get_current_user, RoleChecker
from app.models.user import User, RoleEnum
from app.modules.vacancy.controller import VacancyController
from app.modules.vacancy.schemas import (
    FacultyCreateRequest, FacultyUpdateRequest, FacultyResponse,
    VacancySuggestRequest, VacancyAssessmentResponse, VacancyConfirmRequest,
    AnomalyAcknowledgeRequest
)
from app.dependencies.institution_scope import verify_institution_access
from app.dependencies.pagination import PaginationParams

router = APIRouter(prefix="/vacancies", tags=["Vacancy Identification (Step 2)"])
controller = VacancyController()

principal_only = RoleChecker([RoleEnum.PRINCIPAL])
admin_or_principal = RoleChecker([RoleEnum.ADMIN, RoleEnum.PRINCIPAL])


def _parse_int_like(value: str, field: str) -> int:
    if value.isdigit():
        return int(value)
    raise HTTPException(status_code=422, detail=f"{field} must be an integer id")

@router.post("/faculty", status_code=status.HTTP_201_CREATED, dependencies=[Depends(principal_only)])
async def add_faculty(
    req: FacultyCreateRequest, 
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    await verify_institution_access(req.institution_id, current_user)
    return await controller.add_faculty(db, current_user, req)

@router.put("/faculty/{faculty_id}", dependencies=[Depends(principal_only)])
async def update_faculty(
    faculty_id: UUID, 
    req: FacultyUpdateRequest, 
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    # Institution check would require fetching faculty first, which controller/service does.
    return await controller.update_faculty(db, current_user, faculty_id, req)

@router.get("/faculty", dependencies=[Depends(admin_or_principal)])
async def get_faculty_list(
    institution_id: str, 
    course_id: Optional[str] = None, 
    academic_year: Optional[str] = None, 
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    inst_id = _parse_int_like(institution_id, "institution_id")
    course_id_int = _parse_int_like(course_id, "course_id") if course_id else None
    await verify_institution_access(inst_id, current_user)
    return await controller.get_faculty_list(db, current_user, inst_id, course_id_int, academic_year, pagination.skip, pagination.limit)

@router.delete("/faculty/{faculty_id}", dependencies=[Depends(principal_only)])
async def delete_faculty(
    faculty_id: UUID, 
    reason: str = Query(...), 
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    return await controller.delete_faculty(db, current_user, faculty_id, reason)

@router.post("/suggest", dependencies=[Depends(principal_only)])
async def suggest_vacancy(
    req: VacancySuggestRequest, 
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    await verify_institution_access(req.institution_id, current_user)
    return await controller.suggest_vacancy(db, current_user, req)

@router.post("/ai-analysis", dependencies=[Depends(principal_only)])
async def ai_vacancy_analysis(
    req: VacancySuggestRequest, 
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Unified AI endpoint for fetching all context and generating vacancy requirements."""
    await verify_institution_access(req.institution_id, current_user)
    return await controller.suggest_vacancy(db, current_user, req)

@router.get("/assessment", dependencies=[Depends(admin_or_principal)], summary="Read-only: Admin can audit, Principal can view own")
async def get_assessment(
    institution_id: str, 
    course_id: str, 
    academic_year: str, 
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    inst_id = _parse_int_like(institution_id, "institution_id")
    course_id_int = _parse_int_like(course_id, "course_id")
    await verify_institution_access(inst_id, current_user)
    return await controller.get_assessment(db, current_user, inst_id, course_id_int, academic_year)

@router.post("/confirm", dependencies=[Depends(principal_only)])
async def confirm_vacancy(
    institution_id: int,
    course_id: int,
    academic_year: str,
    req: VacancyConfirmRequest, 
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    await verify_institution_access(institution_id, current_user)
    return await controller.confirm_vacancy(db, current_user, institution_id, course_id, academic_year, req)

@router.post("/anomalies/{anomaly_id}/acknowledge", dependencies=[Depends(principal_only)])
async def acknowledge_anomaly(
    anomaly_id: UUID, 
    req: AnomalyAcknowledgeRequest, 
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    return await controller.acknowledge_anomaly(db, current_user, anomaly_id, req)
