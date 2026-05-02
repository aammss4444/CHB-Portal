from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import RoleChecker, get_current_user
from app.db.session import get_db
from app.models.user import RoleEnum, User
from app.modules.candidate.controller import CandidateController
from app.modules.candidate.schemas import (
    CandidateProfileRequest,
    ExperienceBulkRequest,
    QualificationBulkRequest,
)


router = APIRouter(tags=["Candidate Profile (Step 4)"])
controller = CandidateController()

candidate_only = RoleChecker([RoleEnum.CANDIDATE])


@router.post("/candidates/profile", dependencies=[Depends(candidate_only)])
async def upsert_profile(
    req: CandidateProfileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.upsert_profile(db, current_user, req)


@router.get("/candidates/profile", dependencies=[Depends(candidate_only)])
async def get_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.get_profile(db, current_user)


@router.post("/candidates/qualifications", dependencies=[Depends(candidate_only)])
async def add_qualifications(
    req: QualificationBulkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.add_qualifications(db, current_user, req)


@router.post("/candidates/experience", dependencies=[Depends(candidate_only)])
async def add_experience(
    req: ExperienceBulkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.add_experience(db, current_user, req)
