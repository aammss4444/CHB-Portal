from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.core.security import get_current_user, RoleChecker
from app.models.user import User, RoleEnum
from app.models.selection_round import SelectionRound
from app.modules.selection.controller import SelectionController
from app.modules.selection.schemas import (
    SelectionRoundCreateRequest,
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

@router.post("/rounds", dependencies=[Depends(principal_only)])
async def create_round(
    req: SelectionRoundCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await controller.create_round(db, current_user, req)

@router.post("/rounds/{round_id}/shortlist", dependencies=[Depends(principal_only)])
async def shortlist_candidates(
    round_id: UUID,
    req: ShortlistRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    round_obj = (await db.execute(select(SelectionRound).where(SelectionRound.id == round_id))).scalars().first()
    if round_obj:
        await verify_institution_access(round_obj.institution_id, current_user)
    return await controller.shortlist_candidates(db, current_user, round_id, req)

@router.get("/rounds/{round_id}/shortlisted", dependencies=[Depends(admin_or_principal)])
async def get_shortlisted(
    round_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    round_obj = (await db.execute(select(SelectionRound).where(SelectionRound.id == round_id))).scalars().first()
    if round_obj and current_user.role == RoleEnum.PRINCIPAL:
        await verify_institution_access(round_obj.institution_id, current_user)
    return await controller.get_shortlisted(db, round_id)

@router.post("/rounds/{round_id}/attendance", dependencies=[Depends(principal_only)])
async def mark_attendance(
    round_id: UUID,
    req: AttendanceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    round_obj = (await db.execute(select(SelectionRound).where(SelectionRound.id == round_id))).scalars().first()
    if round_obj:
        await verify_institution_access(round_obj.institution_id, current_user)
    return await controller.mark_attendance(db, current_user, round_id, req)

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
    # Check institution access via service or controller? Controller can do it if we fetch mark first.
    return await controller.update_marks(db, current_user, mark_id, req)

@router.post("/rounds/{round_id}/rank", dependencies=[Depends(principal_only)])
async def generate_rankings(
    round_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    round_obj = (await db.execute(select(SelectionRound).where(SelectionRound.id == round_id))).scalars().first()
    if round_obj:
        await verify_institution_access(round_obj.institution_id, current_user)
    return await controller.generate_rankings(db, current_user, round_id)

@router.get("/rounds/{round_id}/ranked-list", dependencies=[Depends(admin_or_principal)])
async def get_ranked_list(
    round_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    round_obj = (await db.execute(select(SelectionRound).where(SelectionRound.id == round_id))).scalars().first()
    if round_obj and current_user.role == RoleEnum.PRINCIPAL:
        await verify_institution_access(round_obj.institution_id, current_user)
    return await controller.get_ranked_list(db, round_id)

@router.post("/rounds/{round_id}/confirm", dependencies=[Depends(principal_only)])
async def confirm_selection(
    round_id: UUID,
    req: ConfirmSelectionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    round_obj = (await db.execute(select(SelectionRound).where(SelectionRound.id == round_id))).scalars().first()
    if round_obj:
        await verify_institution_access(round_obj.institution_id, current_user)
    return await controller.confirm_selection(db, current_user, round_id, req)

@router.get("/results/{advertisement_id}", dependencies=[Depends(admin_or_principal)])
async def get_final_results(
    advertisement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await controller.get_final_results(db, advertisement_id)


@router.post("/rounds/{round_id}/ai-analysis", dependencies=[Depends(principal_only)])
async def run_ai_analysis(
    round_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    round_obj = (await db.execute(select(SelectionRound).where(SelectionRound.id == round_id))).scalars().first()
    if round_obj:
        await verify_institution_access(round_obj.institution_id, current_user)
    return await controller.run_ai_selection_analysis(db, round_id)


@router.get("/rounds/{round_id}/dashboard", dependencies=[Depends(admin_or_principal)])
async def get_dashboard(
    round_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    round_obj = (await db.execute(select(SelectionRound).where(SelectionRound.id == round_id))).scalars().first()
    if round_obj and current_user.role == RoleEnum.PRINCIPAL:
        await verify_institution_access(round_obj.institution_id, current_user)
    return await controller.get_selection_dashboard(db, round_id)


@router.post("/rounds/{round_id}/ai-snapshot", dependencies=[Depends(principal_only)])
async def create_ai_snapshot(
    round_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    round_obj = (await db.execute(select(SelectionRound).where(SelectionRound.id == round_id))).scalars().first()
    if round_obj:
        await verify_institution_access(round_obj.institution_id, current_user)
    return await controller.create_ai_snapshot(db, current_user, round_id)
