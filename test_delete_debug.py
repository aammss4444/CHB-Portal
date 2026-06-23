import asyncio
import traceback
from sqlalchemy import select, text
from app.db.session import AsyncSessionLocal
from app.models.institution import Institution

async def main():
    async with AsyncSessionLocal() as session:
        institution_id = 1

        # First check what data exists for this institution
        tables_to_check = [
            "lecture_log_audit", "bill_audit", "payment_transaction",
            "appointment_audit", "advertisement_audit", "published_advertisements",
            "shortlisted_candidates", "selection_ai_snapshots", "application_documents",
            "bill_line_item", "bill_approval", "appointment_acceptances",
            "scoring_weight_configs", "vacancy_anomalies", "selection_results",
            "advertisements", "vacancy_assessments", "chb_bill",
            "appointment_letters", "applications", "candidate_scores",
            "interview_marks", "timetable_slots", "daily_attendance_summary",
            "attendance_anomalies", "lecture_logs", "rate_master",
            "existing_faculty", "faculty_credentials", "academic_calendar",
            "norms", "intakes", "courses", "users"
        ]

        print("=== Checking data for institution_id =", institution_id, "===")
        for table in tables_to_check:
            try:
                # Check if institution_id column exists
                result = await session.execute(
                    text(f"SELECT COUNT(*) FROM {table} WHERE institution_id = :id"),
                    {"id": institution_id}
                )
                count = result.scalar()
                if count > 0:
                    print(f"  {table}: {count} rows")
            except Exception as e:
                # Try without institution_id filter
                err_msg = str(e).split('\n')[0]
                print(f"  {table}: ERROR - {err_msg}")
            finally:
                await session.rollback()

        print("\n=== Now trying nested_queries deletion ===")
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
                    res = await session.execute(text(query), {"id": institution_id})
                    if res.rowcount > 0:
                        print(f"  DELETED {res.rowcount} from: {query.split('FROM')[1].split('WHERE')[0].strip()}")
            except Exception as e:
                err_msg = str(e).split('\n')[0]
                print(f"  FAILED: {query.split('FROM')[1].split('WHERE')[0].strip()} - {err_msg}")

        print("\n=== Now trying main tables deletion ===")
        tables_to_clear = [
            "vacancy_anomalies", "selection_results", "advertisements", "vacancy_assessments",
            "chb_bill", "appointment_letters", "applications", "candidate_scores", "interview_marks",
            "timetable_slots", "daily_attendance_summary", "attendance_anomalies", "lecture_logs",
            "rate_master", "existing_faculty", "faculty_credentials", "academic_calendar",
            "norms", "intakes", "courses"
        ]

        progress = True
        pass_num = 0
        while progress:
            progress = False
            pass_num += 1
            print(f"  --- Pass {pass_num} ---")
            for table in tables_to_clear:
                try:
                    async with session.begin_nested():
                        res = await session.execute(text(f"DELETE FROM {table} WHERE institution_id = :id"), {"id": institution_id})
                        if res.rowcount > 0:
                            progress = True
                            print(f"    DELETED {res.rowcount} from {table}")
                except Exception as e:
                    err_msg = str(e).split('\n')[0]
                    print(f"    FAILED {table}: {err_msg}")

        print("\n=== Trying to unlink users ===")
        try:
            async with session.begin_nested():
                res = await session.execute(text("UPDATE users SET institution_id = NULL WHERE institution_id = :id"), {"id": institution_id})
                print(f"  Unlinked {res.rowcount} users")
        except Exception as e:
            print(f"  FAILED unlinking users: {e}")

        print("\n=== Now trying to delete institution itself ===")
        try:
            result = await session.execute(select(Institution).filter(Institution.id == institution_id))
            inst = result.scalars().first()
            if inst:
                await session.delete(inst)
                await session.commit()
                print("  SUCCESS! Institution deleted.")
            else:
                print("  Institution not found!")
        except Exception as e:
            await session.rollback()
            print(f"  FAILED: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(main())
