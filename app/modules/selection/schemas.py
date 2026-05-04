from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field

class ShortlistRequest(BaseModel):
    application_ids: List[UUID]
    remarks: Optional[str] = None

class AttendanceItem(BaseModel):
    application_id: UUID
    is_present: bool

class AttendanceRequest(BaseModel):
    attendance: List[AttendanceItem]

class InterviewMarksRequest(BaseModel):
    advertisement_id: UUID
    application_id: UUID
    candidate_id: UUID
    institution_id: int
    subject_knowledge: Decimal = Field(..., ge=0, le=100)
    teaching_aptitude: Decimal = Field(..., ge=0, le=100)
    communication_skills: Decimal = Field(..., ge=0, le=100)
    overall_impression: Decimal = Field(..., ge=0, le=100)

class InterviewMarksUpdateRequest(BaseModel):
    subject_knowledge: Optional[Decimal] = Field(None, ge=0, le=100)
    teaching_aptitude: Optional[Decimal] = Field(None, ge=0, le=100)
    communication_skills: Optional[Decimal] = Field(None, ge=0, le=100)
    overall_impression: Optional[Decimal] = Field(None, ge=0, le=100)

class ConfirmSelectionRequest(BaseModel):
    remarks: str

class ShortlistedCandidateResponse(BaseModel):
    application_id: UUID
    candidate_id: UUID
    candidate_name: str
    application_number: str
    qualification: str
    experience_years: float
    is_present: bool
    interview_total: Optional[Decimal] = None

    class Config:
        from_attributes = True

class RankedCandidateResponse(BaseModel):
    rank: int
    candidate_name: str
    application_id: UUID
    final_score: Decimal
    result_status: str
    waitlist_position: Optional[int] = None
    score_breakdown: Dict[str, Any]
    qualification: str
    experience_years: float

class SelectionResultSummary(BaseModel):
    selected_count: int
    waitlisted_count: int
    rejected_count: int

class GroupedSelectionResults(BaseModel):
    SELECTED: List[Dict[str, Any]]
    WAITLISTED: List[Dict[str, Any]]
    REJECTED: List[Dict[str, Any]]
