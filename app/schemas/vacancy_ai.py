from pydantic import BaseModel
from typing import List

class VacancyAIResponse(BaseModel):
    ai_suggested_vacancy: int
    overloaded: List[str]
    underutilized: List[str]
    justification: str
    insights: List[str]
    confidence_score: float = 0.9
