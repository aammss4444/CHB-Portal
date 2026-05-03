from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.modules.scoring_weights.service import ScoringWeightService
from app.modules.scoring_weights.schemas import (
    ScoringWeightCreateRequest,
    PrincipalWeightOverrideRequest,
    ScoringWeightResponse,
    WeightResolveResponse
)

class ScoringWeightController:
    def __init__(self):
        self.service = ScoringWeightService()

    async def create_global_config(
        self, db: AsyncSession, current_user: User, req: ScoringWeightCreateRequest
    ) -> dict:
        config = await self.service.create_global_config(db, current_user, req)
        return {"status": "success", "data": ScoringWeightResponse.from_orm(config)}

    async def override_advertisement_weights(
        self, db: AsyncSession, current_user: User, advertisement_id: UUID, req: PrincipalWeightOverrideRequest
    ) -> dict:
        config = await self.service.override_advertisement_weights(db, current_user, advertisement_id, req)
        return {
            "status": "success", 
            "data": ScoringWeightResponse.from_orm(config),
            "message": "Advertisement override saved successfully. This will take priority during ranking."
        }

    async def get_active_configs(self, db: AsyncSession) -> dict:
        configs = await self.service.get_active_configs(db)
        return {"status": "success", "data": [ScoringWeightResponse.from_orm(c) for c in configs]}

    async def resolve_weights(
        self, db: AsyncSession, course_id: int, level: str, advertisement_id: UUID
    ) -> dict:
        config, priority = await self.service.resolve_weights(db, course_id, level, advertisement_id)
        return {
            "status": "success",
            "data": {
                "matched_priority": priority,
                "config": ScoringWeightResponse.from_orm(config)
            }
        }

    async def delete_config(self, db: AsyncSession, config_id: UUID) -> dict:
        await self.service.delete_config(db, config_id)
        return {"status": "success", "message": "Config soft-deleted successfully"}
