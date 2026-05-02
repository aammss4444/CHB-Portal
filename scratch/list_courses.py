
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def list_courses():
    engine = create_async_engine("postgresql+asyncpg://postgres:Amey%40p4444@localhost:5432/chb_portal")
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT * FROM courses LIMIT 10"))
        rows = res.fetchall()
        print("Courses:")
        for r in rows:
            print(f" - {r._asdict()}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(list_courses())
