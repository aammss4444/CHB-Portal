from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, RoleEnum
from app.models.existing_faculty import ExistingFaculty
from app.models.vacancy_assessment import VacancyAssessment
from app.models.application import Application, ApplicationStatus
from app.models.shortlisted_candidate import ShortlistedCandidate
from app.models.candidate import Candidate
from app.models.advertisement import Advertisement
from app.models.institution import Institution
from typing import Dict, Any, List

class PrincipalService:
    async def get_dashboard_stats(self, db: AsyncSession, current_user: User) -> Dict[str, Any]:
        institution_id = current_user.institution_id
        if not institution_id:
            return {
                "stats": {
                    "total_faculty": 0,
                    "vacancies_identified": 0,
                    "live_applications": 0,
                    "scheduled_interviews": 0,
                    "faculty_trend": "0 this month",
                    "vacancy_trend": "No data",
                    "application_trend": "0 new today",
                    "interview_trend": "None scheduled",
                    "institute_latitude": None,
                    "institute_longitude": None
                },
                "recent_applications": []
            }

        # 1. Total Faculty
        stmt_faculty = select(func.count(ExistingFaculty.id)).where(
            and_(ExistingFaculty.institution_id == institution_id, ExistingFaculty.status == "ACTIVE")
        )
        total_faculty = (await db.execute(stmt_faculty)).scalar() or 0

        # 2. Vacancies Identified
        stmt_vacancies = select(func.sum(VacancyAssessment.suggested_vacancy)).where(
            and_(VacancyAssessment.institution_id == institution_id, VacancyAssessment.status != "COMPLETED")
        )
        vacancies_identified = (await db.execute(stmt_vacancies)).scalar() or 0

        # 3. Live Applications (SUBMITTED, UNDER_REVIEW)
        stmt_apps = select(func.count(Application.id)).where(
            and_(
                Application.institution_id == institution_id,
                Application.status.in_([ApplicationStatus.SUBMITTED.value, ApplicationStatus.UNDER_REVIEW.value])
            )
        )
        live_applications = (await db.execute(stmt_apps)).scalar() or 0

        # 4. Scheduled Interviews (Shortlisted but not yet marked)
        # For now, we'll count candidates in ShortlistedCandidate table for active advertisements
        stmt_interviews = select(func.count(ShortlistedCandidate.id)).join(Advertisement).where(
            and_(
                Advertisement.institution_id == institution_id,
                Advertisement.status == "PUBLISHED"
            )
        )
        scheduled_interviews = (await db.execute(stmt_interviews)).scalar() or 0

        # 5. Recent Applications
        stmt_recent = select(
            Application.id,
            Candidate.full_name,
            Application.applied_designation,
            Application.status,
            Application.ai_confidence_score
        ).join(Candidate, Application.candidate_id == Candidate.id).where(
            Application.institution_id == institution_id
        ).order_by(Application.submitted_at.desc()).limit(5)
        
        recent_rows = (await db.execute(stmt_recent)).all()
        recent_applications = [
            {
                "id": f"APP-{str(row[0])[:4].upper()}",
                "name": row[1],
                "post": row[2],
                "status": row[3],
                "score": float(row[4] or 0)
            } for row in recent_rows
        ]

        institution = await db.get(Institution, institution_id)

        return {
            "stats": {
                "total_faculty": total_faculty,
                "vacancies_identified": int(vacancies_identified),
                "live_applications": live_applications,
                "scheduled_interviews": scheduled_interviews,
                "faculty_trend": "+0 this month",
                "vacancy_trend": "Audit pending",
                "application_trend": "New applications live",
                "interview_trend": "In progress",
                "institute_latitude": institution.latitude if institution else None,
                "institute_longitude": institution.longitude if institution else None
            },
            "recent_applications": recent_applications
        }

    async def set_institute_location(self, db: AsyncSession, current_user: User, latitude: float, longitude: float):
        if not current_user.institution_id:
            return {"status": "error", "message": "No institution assigned"}
            
        institution = await db.get(Institution, current_user.institution_id)
        if not institution:
            return {"status": "error", "message": "Institution not found"}
            
        institution.latitude = latitude
        institution.longitude = longitude
        await db.commit()
        return {"status": "success"}
