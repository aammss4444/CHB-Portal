from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.security import get_current_user, RoleChecker
from app.models.user import User, RoleEnum
from app.modules.scoring_weights.controller import ScoringWeightController
from app.modules.scoring_weights.schemas import (
    ScoringWeightCreateRequest,
    PrincipalWeightOverrideRequest,
)
from app.dependencies.institution_scope import verify_institution_access
from app.models.advertisement import Advertisement
from sqlalchemy import select

router = APIRouter(prefix="/scoring-weights", tags=["Scoring Weight Configuration (Step 5)"])
controller = ScoringWeightController()

admin_only = RoleChecker([RoleEnum.ADMIN])
principal_only = RoleChecker([RoleEnum.PRINCIPAL])
admin_or_principal = RoleChecker([RoleEnum.ADMIN, RoleEnum.PRINCIPAL])

@router.post("", dependencies=[Depends(admin_only)])
async def create_global_config(
    req: ScoringWeightCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await controller.create_global_config(db, current_user, req)

@router.post("/advertisement/{advertisement_id}", dependencies=[Depends(principal_only)])
async def override_advertisement_weights(
    advertisement_id: UUID,
    req: PrincipalWeightOverrideRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify institution access
    ad = (await db.execute(select(Advertisement).where(Advertisement.id == advertisement_id))).scalars().first()
    if not ad:
        controller.service._raise_error(404, "ADVERTISEMENT_NOT_FOUND", "Advertisement not found")
    await verify_institution_access(ad.institution_id, current_user)
    
    return await controller.override_advertisement_weights(db, current_user, advertisement_id, req)

@router.get("", dependencies=[Depends(admin_only)])
async def get_active_configs(db: AsyncSession = Depends(get_db)):
    return await controller.get_active_configs(db)

@router.get("/resolve", dependencies=[Depends(admin_or_principal)])
async def resolve_weights(
    course_id: int = Query(...),
    level: str = Query(...),
    advertisement_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    return await controller.resolve_weights(db, course_id, level, advertisement_id)

@router.delete("/{config_id}", dependencies=[Depends(admin_only)])
async def delete_config(
    config_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    return await controller.delete_config(db, config_id)
