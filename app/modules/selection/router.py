from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.core.security import get_current_user, RoleChecker
from app.models.user import User, RoleEnum
from app.models.advertisement import Advertisement
from app.modules.selection.controller import SelectionController
from app.modules.selection.schemas import (
    ShortlistRequest,
    AttendanceRequest,
    InterviewMarksRequest,
    InterviewMarksUpdateRequest,
    ConfirmSelectionRequest
)
from app.dependencies.institution_scope import verify_institution_access

router = APIRouter(prefix="/selection", tags=["Selection Process (Step 5)"])
controller = SelectionController()

principal_only = RoleChecker([RoleEnum.PRINCIPAL])
admin_or_principal = RoleChecker([RoleEnum.ADMIN, RoleEnum.PRINCIPAL])

@router.get("/results", dependencies=[Depends(admin_or_principal)])
async def get_all_results(
    status: str | None = None,
    result_status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role == RoleEnum.PRINCIPAL:
        return await controller.get_all_results(db, current_user.institution_id, status, result_status)
    return await controller.get_all_results(db, None, status, result_status)

async def check_ad_access(db: AsyncSession, current_user: User, advertisement_id: UUID):
    ad_obj = (await db.execute(select(Advertisement).where(Advertisement.id == advertisement_id))).scalars().first()
    if ad_obj and current_user.role == RoleEnum.PRINCIPAL:
        await verify_institution_access(ad_obj.institution_id, current_user)

@router.post("/{advertisement_id}/shortlist", dependencies=[Depends(principal_only)])
async def shortlist_candidates(
    advertisement_id: UUID,
    req: ShortlistRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await check_ad_access(db, current_user, advertisement_id)
    return await controller.shortlist_candidates(db, current_user, advertisement_id, req)

@router.get("/{advertisement_id}/shortlisted", dependencies=[Depends(admin_or_principal)])
async def get_shortlisted(
    advertisement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await check_ad_access(db, current_user, advertisement_id)
    return await controller.get_shortlisted(db, advertisement_id)

@router.post("/{advertisement_id}/attendance", dependencies=[Depends(principal_only)])
async def mark_attendance(
    advertisement_id: UUID,
    req: AttendanceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await check_ad_access(db, current_user, advertisement_id)
    return await controller.mark_attendance(db, current_user, advertisement_id, req)

@router.post("/marks", dependencies=[Depends(principal_only)])
async def enter_marks(
    req: InterviewMarksRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await verify_institution_access(req.institution_id, current_user)
    return await controller.enter_marks(db, current_user, req)

@router.put("/marks/{mark_id}", dependencies=[Depends(principal_only)])
async def update_marks(
    mark_id: UUID,
    req: InterviewMarksUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await controller.update_marks(db, current_user, mark_id, req)

@router.post("/{advertisement_id}/rank", dependencies=[Depends(principal_only)])
async def generate_rankings(
    advertisement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await check_ad_access(db, current_user, advertisement_id)
    return await controller.generate_rankings(db, current_user, advertisement_id)

@router.get("/{advertisement_id}/ranked-list", dependencies=[Depends(admin_or_principal)])
async def get_ranked_list(
    advertisement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await check_ad_access(db, current_user, advertisement_id)
    return await controller.get_ranked_list(db, advertisement_id)

@router.post("/{advertisement_id}/confirm", dependencies=[Depends(principal_only)])
async def confirm_selection(
    advertisement_id: UUID,
    req: ConfirmSelectionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await check_ad_access(db, current_user, advertisement_id)
    return await controller.confirm_selection(db, current_user, advertisement_id, req)

@router.get("/results/{advertisement_id}", dependencies=[Depends(admin_or_principal)])
async def get_final_results(
    advertisement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await controller.get_final_results(db, advertisement_id)

@router.post("/{advertisement_id}/ai-analysis", dependencies=[Depends(principal_only)])
async def run_ai_analysis(
    advertisement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await check_ad_access(db, current_user, advertisement_id)
    return await controller.run_ai_selection_analysis(db, advertisement_id)

@router.get("/{advertisement_id}/dashboard", dependencies=[Depends(admin_or_principal)])
async def get_dashboard(
    advertisement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await check_ad_access(db, current_user, advertisement_id)
    return await controller.get_selection_dashboard(db, advertisement_id)

@router.post("/{advertisement_id}/ai-snapshot", dependencies=[Depends(principal_only)])
async def create_ai_snapshot(
    advertisement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await check_ad_access(db, current_user, advertisement_id)
    return await controller.create_ai_snapshot(db, current_user, advertisement_id)
