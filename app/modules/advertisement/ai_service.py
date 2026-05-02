from typing import Dict, Any

from app.modules.advertisement.ai_engine import AdvertisementAIEngine


class AdvertisementAIService:
    def __init__(self, engine: AdvertisementAIEngine):
        self.engine = engine

    async def generate(self, payload: Dict[str, Any]):
        return await self.engine.create_ad(payload)
