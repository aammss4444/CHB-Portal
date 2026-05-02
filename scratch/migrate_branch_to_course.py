
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = "postgresql+asyncpg://postgres:Amey%40p4444@localhost:5432/chb_portal"

TABLES_TO_FIX = [
    "intake_definitions",
    "lecture_logs",
    "selection_results",
    "appointment_letters",
    "daily_attendance_summary",
    "vacancy_assessments",
    "existing_faculty",
    "selection_rounds",
    "applications",
    "chb_bill",
    "advertisements",
    "scoring_weight_configs",
    "timetable_slots"
]

async def migrate():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        for table in TABLES_TO_FIX:
            print(f"Processing table: {table}")
            
            # Check if branch_id exists
            res = await conn.execute(text(f"""
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = '{table}' AND column_name = 'branch_id'
            """))
            if not res.fetchone():
                print(f" - column 'branch_id' not found in '{table}', skipping.")
                continue

            # Find and drop foreign key constraints on branch_id
            res = await conn.execute(text(f"""
                SELECT constraint_name 
                FROM information_schema.key_column_usage 
                WHERE table_name = '{table}' AND column_name = 'branch_id'
                AND constraint_name IN (
                    SELECT constraint_name FROM information_schema.table_constraints 
                    WHERE table_name = '{table}' AND constraint_type = 'FOREIGN KEY'
                )
            """))
            fks = res.fetchall()
            for fk in fks:
                constraint_name = fk[0]
                print(f" - Dropping FK constraint: {constraint_name}")
                await conn.execute(text(f'ALTER TABLE {table} DROP CONSTRAINT "{constraint_name}"'))

            # Rename branch_id to course_id
            print(f" - Renaming branch_id to course_id")
            await conn.execute(text(f"ALTER TABLE {table} RENAME COLUMN branch_id TO course_id"))

            # Add new foreign key constraint to courses.id
            print(f" - Adding FK constraint to courses.id")
            await conn.execute(text(f"""
                ALTER TABLE {table} 
                ADD CONSTRAINT fk_{table}_course_id 
                FOREIGN KEY (course_id) REFERENCES courses(id)
            """))

    await engine.dispose()
    print("Migration completed.")

if __name__ == "__main__":
    asyncio.run(migrate())
