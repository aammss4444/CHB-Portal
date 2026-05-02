from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.modules.helpdesk.controller import HelpdeskController
from app.modules.helpdesk.schemas import HelpdeskQueryRequest

router = APIRouter(prefix="/helpdesk", tags=["AI Helpdesk (Step 10)"])
controller = HelpdeskController()


@router.post("/query")
async def query_helpdesk(
    req: HelpdeskQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controller.query(db, current_user, req)
