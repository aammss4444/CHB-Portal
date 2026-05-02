from typing import List, Dict, Any
from app.modules.application.ai_engine import DocumentAIEngine

class DocumentAIService:
    def __init__(self, engine: DocumentAIEngine):
        self.engine = engine

    async def process(self, documents, profile: Dict[str, Any]) -> Dict[str, Any]:
        return await self.engine.analyze(documents, profile)

    async def process_application(self, documents, profile: Dict[str, Any]) -> Dict[str, Any]:
        return await self.process(documents, profile)
