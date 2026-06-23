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
            nested_queries = [
                "DELETE FROM lecture_log_audit WHERE lecture_log_id IN (SELECT id FROM lecture_logs WHERE institution_id = :id)",
                "DELETE FROM bill_audit WHERE bill_id IN (SELECT id FROM chb_bill WHERE institution_id = :id)",
                "DELETE FROM payment_transaction WHERE bill_id IN (SELECT id FROM chb_bill WHERE institution_id = :id)",
                "DELETE FROM appointment_audit WHERE appointment_letter_id IN (SELECT id FROM appointment_letters WHERE institution_id = :id)",
                "DELETE FROM advertisement_audit WHERE advertisement_id IN (SELECT id FROM advertisements WHERE institution_id = :id)",
                "DELETE FROM published_advertisements WHERE advertisement_id IN (SELECT id FROM advertisements WHERE institution_id = :id)",
                "DELETE FROM shortlisted_candidates WHERE advertisement_id IN (SELECT id FROM advertisements WHERE institution_id = :id)",
                "DELETE FROM selection_ai_snapshots WHERE advertisement_id IN (SELECT id FROM advertisements WHERE institution_id = :id)",
                "DELETE FROM application_documents WHERE application_id IN (SELECT id FROM applications WHERE institution_id = :id)",
                "DELETE FROM bill_line_item WHERE bill_id IN (SELECT id FROM chb_bill WHERE institution_id = :id)",
                "DELETE FROM bill_approval WHERE bill_id IN (SELECT id FROM chb_bill WHERE institution_id = :id)",
                "DELETE FROM appointment_acceptances WHERE appointment_letter_id IN (SELECT id FROM appointment_letters WHERE institution_id = :id)",
                "DELETE FROM scoring_weight_configs WHERE advertisement_id IN (SELECT id FROM advertisements WHERE institution_id = :id)"
            ]
            for query in nested_queries:
                try:
                    async with session.begin_nested():
                        await session.execute(text(query), {"id": institution_id})
                except Exception as e:
                    pass
            
            tables_to_clear = [
                "vacancy_anomalies", "selection_results", "advertisements", "vacancy_assessments",
                "chb_bill", "appointment_letters", "applications", "candidate_scores", "interview_marks",
                "timetable_slots", "daily_attendance_summary", "attendance_anomalies", "lecture_logs",
                "rate_master", "existing_faculty", "faculty_credentials", "academic_calendar"
            ]
            
            # Keep trying to delete tables until we do a full pass without any successful deletes
            progress = True
            while progress:
                progress = False
                for table in tables_to_clear:
                    try:
                        async with session.begin_nested():
                            res = await session.execute(text(f"DELETE FROM {table} WHERE institution_id = :id"), {"id": institution_id})
                            if res.rowcount > 0:
                                progress = True
                                print(f"Deleted {res.rowcount} from {table}")
                    except Exception as e:
                        pass # FK violation, will try again next pass

            await session.delete(inst)
            await session.commit()
            print("Deleted successfully!")
        except Exception as e:
            print("Exception during deletion:")
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
