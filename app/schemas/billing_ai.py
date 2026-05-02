from pydantic import BaseModel
from typing import List

class BillingIssue(BaseModel):
    type: str
    severity: str
    description: str

class BillingAIResponse(BaseModel):
    validation_status: str
    issues: List[BillingIssue]
    approval_probability: float
    risk_level: str
    treasury_flags: List[str]
    insights: List[str]
    confidence_score: float

