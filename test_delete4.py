import asyncio
from sqlalchemy import select, delete
from app.db.session import AsyncSessionLocal
from app.models.institution import Institution
from app.models.vacancy_assessment import VacancyAssessment
from app.models.vacancy_anomaly import VacancyAnomaly
import traceback

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Institution).filter(Institution.id == 8))
        inst = result.scalars().first()
        if not inst:
            print("Inst 8 not found")
            return
        
        print(f"Found inst 8 ({inst.name}). Deleting...")
        try:
            # 1. Clear Vacancy Anomaly
            await session.execute(delete(VacancyAnomaly).where(VacancyAnomaly.institution_id == inst.id))
            # 2. Clear Vacancy Assessment
            await session.execute(delete(VacancyAssessment).where(VacancyAssessment.institution_id == inst.id))

            await session.delete(inst)
            await session.commit()
            print("Deleted successfully!")
        except Exception as e:
            print("Exception during deletion:")
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
