from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RankingSuggestion(BaseModel):
    application_id: UUID
    suggested_rank: int
    reason: str


class BiasFlag(BaseModel):
    type: str  # UNIFORM_INTERVIEW_MARKS, QUALIFICATION_MISMATCH, RESERVATION_IMBALANCE
    severity: str  # LOW, MEDIUM, HIGH
    description: str


class SelectionAIResponse(BaseModel):
    ranking_suggestions: List[RankingSuggestion] = Field(default_factory=list)
    bias_flags: List[BiasFlag] = Field(default_factory=list)
    insights: List[str] = Field(default_factory=list)
    confidence_score: float = Field(0.5, ge=0.0, le=1.0)


class DashboardCandidate(BaseModel):
    rank: int
    candidate_name: str
    final_score: float
    result_status: str


class ScoreDistribution(BaseModel):
    range: str
    count: int


class SelectionDashboardResponse(BaseModel):
    top_candidates: List[DashboardCandidate]
    score_distribution: List[ScoreDistribution]
    bias_flags: List[BiasFlag]
    insights: List[str]
