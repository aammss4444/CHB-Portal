from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.modules.audit.service import AuditService


class AuditController:
    def __init__(self) -> None:
        self.service = AuditService()

    async def get_ai_report(self, db: AsyncSession, current_user: User, days: int):
        data = await self.service.get_ai_report(db, current_user, days)
        return {"status": "success", "data": data}
