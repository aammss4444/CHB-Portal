from pydantic import BaseModel
from typing import List

class Anomaly(BaseModel):
    type: str
    severity: str
    description: str

class AttendanceAIResponse(BaseModel):
    anomalies: List[Anomaly]
    patterns: List[str]
    risk_level: str
    insights: List[str]
    confidence_score: float

class AICheckResponse(BaseModel):
    status: str
    data: AttendanceAIResponse

class HighRiskFaculty(BaseModel):
    faculty_id: int
    risk_level: str

class AIMonitorResponse(BaseModel):
    high_risk_faculty: List[HighRiskFaculty]
    common_patterns: List[str]
    summary: str
