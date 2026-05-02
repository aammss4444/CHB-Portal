
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def peek_data():
    engine = create_async_engine("postgresql+asyncpg://postgres:Amey%40p4444@localhost:5432/chb_portal")
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT * FROM intake_definitions WHERE id = 1"))
        row = res.fetchone()
        print(f"Row 1 in intake_definitions: {row._asdict() if row else 'Not found'}")
        
        if row:
            branch_id = row.branch_id
            res = await conn.execute(text(f"SELECT * FROM branches WHERE id = {branch_id}"))
            branch = res.fetchone()
            print(f"Branch for ID {branch_id}: {branch._asdict() if branch else 'Not found'}")
            
            # Check if there is a corresponding course
            if branch:
                branch_name = branch.name
                res = await conn.execute(text("SELECT * FROM courses WHERE name = :name"), {"name": branch_name})
                course = res.fetchone()
                print(f"Course with name '{branch_name}': {course._asdict() if course else 'Not found'}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(peek_data())
