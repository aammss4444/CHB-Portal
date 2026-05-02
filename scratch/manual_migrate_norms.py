
import asyncio
from sqlalchemy import text
from app.db.session import engine

async def run_migrations():
    async with engine.begin() as conn:
        print("Running hotfix for Norms table updates...")
        await conn.execute(text("ALTER TABLE norms ADD COLUMN IF NOT EXISTS academic_year VARCHAR"))
        await conn.execute(text("ALTER TABLE norms ADD COLUMN IF NOT EXISTS course_level VARCHAR"))
        await conn.execute(text("ALTER TABLE norms ADD COLUMN IF NOT EXISTS branch_id INTEGER"))
        await conn.execute(text("ALTER TABLE norms ADD COLUMN IF NOT EXISTS faculty_student_ratio FLOAT"))
        await conn.execute(text("ALTER TABLE norms ADD COLUMN IF NOT EXISTS min_qualification VARCHAR"))
        await conn.execute(text("ALTER TABLE norms ADD COLUMN IF NOT EXISTS max_daily_lectures INTEGER DEFAULT 6"))
        await conn.execute(text("ALTER TABLE norms ADD COLUMN IF NOT EXISTS credit_to_hour_ratio FLOAT DEFAULT 1.0"))
        
        print("Migrating data...")
        await conn.execute(text("UPDATE norms SET course_level = level WHERE course_level IS NULL"))
        await conn.execute(text("UPDATE norms SET faculty_student_ratio = ratio WHERE faculty_student_ratio IS NULL"))
        print("Migration complete!")

if __name__ == "__main__":
    asyncio.run(run_migrations())
