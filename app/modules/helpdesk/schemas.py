from __future__ import annotations

from pydantic import BaseModel, Field


class HelpdeskQueryRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)


class HelpdeskQueryResponse(BaseModel):
    answer: str
    confidence: float
    language: str
