from __future__ import annotations

from typing import Any, Dict

from app.modules.helpdesk.ai_engine import HelpdeskAIEngine


class HelpdeskAIService:
    def __init__(self, engine: HelpdeskAIEngine):
        self.engine = engine

    async def process_query(self, question: str) -> Dict[str, Any]:
        return await self.engine.answer_query(question)
