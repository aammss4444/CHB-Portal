import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def reset():
    async with AsyncSessionLocal() as db:
        await db.execute(text("TRUNCATE interview_marks CASCADE"))
        await db.execute(text("TRUNCATE selection_results CASCADE"))
        await db.execute(text("TRUNCATE candidate_scores CASCADE"))
        await db.execute(text("TRUNCATE shortlisted_candidates CASCADE"))
        await db.execute(text("TRUNCATE selection_rounds CASCADE"))
        # Also clean up anomalies for rounds
        await db.execute(text("DELETE FROM vacancy_anomalies WHERE round_id IS NOT NULL"))
        # Reset application statuses to SUBMITTED if they were UNDER_REVIEW or SHORTLISTED
        await db.execute(text("UPDATE applications SET status = 'SUBMITTED' WHERE status IN ('UNDER_REVIEW', 'SHORTLISTED')"))
        await db.commit()
        print("Step 5 tables reset successfully.")

if __name__ == "__main__":
    asyncio.run(reset())
