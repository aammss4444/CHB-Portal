
import asyncio
import sys
import os

# Add the backend directory to sys.path
sys.path.append(os.path.abspath('.'))

from app.db.session import AsyncSessionLocal as SessionLocal
from sqlalchemy import select
from app.models.vacancy_assessment import VacancyAssessment
from sqlalchemy.orm import selectinload

async def check():
    async with SessionLocal() as db:
        stmt = select(VacancyAssessment).filter(
            VacancyAssessment.institution_id == 3, 
            VacancyAssessment.course_id == 3, 
            VacancyAssessment.academic_year == '2026-27'
        ).options(selectinload(VacancyAssessment.anomalies))
        res = await db.execute(stmt)
        ass = res.scalars().first()
        if not ass:
            print("Assessment not found")
            return
        
        print(f"Status: {ass.status}")
        for a in ass.anomalies:
            print(f"ID: {a.id} | Type: {a.anomaly_type} | Severity: {a.severity} | Ack: {a.is_acknowledged}")

if __name__ == "__main__":
    asyncio.run(check())
