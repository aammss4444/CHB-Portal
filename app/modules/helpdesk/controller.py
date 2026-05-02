from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.modules.helpdesk.ai_engine import HelpdeskAIEngine
from app.modules.helpdesk.ai_service import HelpdeskAIService
from app.modules.helpdesk.schemas import HelpdeskQueryRequest


class HelpdeskController:
    def __init__(self) -> None:
        self.ai_service = HelpdeskAIService(HelpdeskAIEngine())

    async def query(self, db: AsyncSession, current_user: User, req: HelpdeskQueryRequest):
        _ = db, current_user
        data = await self.ai_service.process_query(req.question)
        return {"status": "success", "data": data}
