from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.modules.principal.service import PrincipalService

class PrincipalController:
    def __init__(self):
        self.service = PrincipalService()

    async def get_dashboard_data(self, db: AsyncSession, current_user: User):
        return await self.service.get_dashboard_stats(db, current_user)
