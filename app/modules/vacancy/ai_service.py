from app.modules.vacancy.ai_engine import VacancyAIEngine
from typing import List, Optional, Dict, Any

class VacancyAIService:
    def __init__(self, engine: VacancyAIEngine):
        self.engine = engine

    async def analyze(self, payload: Dict[str, Any], faculty_list: List[Dict[str, Any]], history: Optional[Dict[str, Any]] = None, norm_info: Dict[str, Any] = None, intake_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Orchestrates the vacancy intelligence analysis.
        """
        return await self.engine.analyze_vacancy(payload, faculty_list, history, norm_info, intake_info)
