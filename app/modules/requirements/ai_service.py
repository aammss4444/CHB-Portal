from app.modules.requirements.ai_engine import RequirementAIEngine
from typing import Optional, Dict, Any

class RequirementAIService:
    def __init__(self, engine: RequirementAIEngine):
        self.engine = engine

    async def validate_with_ai(self, payload: Dict[str, Any], history: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Orchestrates AI validation by calling the engine.
        """
        return await self.engine.analyze_requirement(payload, history)
