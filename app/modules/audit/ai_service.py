from __future__ import annotations

from typing import Any, Dict, List

from app.modules.audit.ai_engine import AuditAIEngine


class AuditAIService:
    def __init__(self, engine: AuditAIEngine):
        self.engine = engine

    async def build_ai_report(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        return await self.engine.generate_report(logs)
