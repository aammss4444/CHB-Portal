import asyncio
from sqlalchemy import select, text
from app.db.session import AsyncSessionLocal
from app.models.institution import Institution
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
            institution_id = inst.id
            tables_to_clear = [
                "chb_bills", "daily_attendance_summaries", "attendance_anomalies", "lecture_logs",
                "timetable_slots", "faculty_credentials", "appointment_letters", "selection_results",
                "candidate_scores", "interview_marks", "applications", "vacancy_anomalies",
                "vacancy_assessments", "rate_master", "existing_faculties", "academic_calendars"
            ]
            for table in tables_to_clear:
                await session.execute(text(f"DELETE FROM {table} WHERE institution_id = :id"), {"id": institution_id})

            await session.delete(inst)
            await session.commit()
            print("Deleted successfully!")
        except Exception as e:
            print("Exception during deletion:")
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
