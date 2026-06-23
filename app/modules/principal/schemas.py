from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import UUID

class DashboardStats(BaseModel):
    total_faculty: int
    vacancies_identified: int
    live_applications: int
    scheduled_interviews: int
    faculty_trend: str
    vacancy_trend: str
    application_trend: str
    interview_trend: str
    institute_latitude: Optional[float] = None
    institute_longitude: Optional[float] = None

class RecentApplication(BaseModel):
    id: str
    name: str
    post: str
    status: str
    score: float

class PrincipalDashboardResponse(BaseModel):
    stats: DashboardStats
    recent_applications: List[RecentApplication]
