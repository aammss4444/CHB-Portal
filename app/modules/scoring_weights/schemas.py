from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

class ScoringWeightBase(BaseModel):
    qualification_weight: Decimal = Field(..., ge=0, le=100)
    experience_weight: Decimal = Field(..., ge=0, le=100)
    interview_weight: Decimal = Field(..., ge=0, le=100)
    publication_weight: Decimal = Field(..., ge=0, le=100)
    reservation_weight: Decimal = Field(..., ge=0, le=100)

    @model_validator(mode="after")
    def validate_sum_to_100(self) -> "ScoringWeightBase":
        total = (
            self.qualification_weight
            + self.experience_weight
            + self.interview_weight
            + self.publication_weight
            + self.reservation_weight
        )
        if total != Decimal("100.00"):
            raise ValueError("WEIGHTS_MUST_SUM_TO_100")
        return self

class ScoringWeightCreateRequest(ScoringWeightBase):
    config_name: str = Field(..., max_length=100)
    course_id: Optional[int] = None
    level: Optional[str] = None # UG, PG, DIPLOMA
    effective_from: date

class PrincipalWeightOverrideRequest(ScoringWeightBase):
    pass

class ScoringWeightResponse(ScoringWeightBase):
    id: UUID
    config_name: str
    course_id: Optional[int] = None
    level: Optional[str] = None
    advertisement_id: Optional[UUID] = None
    set_by_role: str
    effective_from: date
    effective_to: Optional[date] = None
    is_active: bool

    class Config:
        from_attributes = True

class WeightResolveResponse(BaseModel):
    matched_priority: int
    config: ScoringWeightResponse
