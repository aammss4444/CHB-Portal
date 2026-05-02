from pydantic import BaseModel
from typing import List

class AIAnomaly(BaseModel):
    type: str
    severity: str
    message: str
    insight: str
    recommendation: str

class AIResponse(BaseModel):
    status: str
    anomalies: List[AIAnomaly]
    insights: List[str]
    confidence_score: float
