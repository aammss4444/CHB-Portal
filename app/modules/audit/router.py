from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import RoleChecker, get_current_user
from app.db.session import get_db
from app.models.user import RoleEnum, User
from app.modules.audit.controller import AuditController

router = APIRouter(prefix="/audit", tags=["Audit & Compliance AI (Step 9)"])
controller = AuditController()

admin_only = RoleChecker([RoleEnum.ADMIN])


@router.get("/ai-report", dependencies=[Depends(admin_only)])
async def get_ai_report(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.get_ai_report(db, current_user, days)
