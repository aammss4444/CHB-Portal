from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.modules.principal.service import PrincipalService

class PrincipalController:
    def __init__(self):
        self.service = PrincipalService()

    async def get_dashboard_data(self, db: AsyncSession, current_user: User):
        return await self.service.get_dashboard_stats(db, current_user)

    async def set_institute_location(self, db: AsyncSession, current_user: User, latitude: float, longitude: float):
        return await self.service.set_institute_location(db, current_user, latitude, longitude)
