from pydantic import BaseModel


class DocumentAIResponse(BaseModel):
    status: str
    scrutiny_summary: str
    missing_documents: list[str]
    mismatches: list[str]
    confidence_score: float
