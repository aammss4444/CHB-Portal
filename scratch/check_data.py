
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check_data():
    engine = create_async_engine("postgresql+asyncpg://postgres:Amey%40p4444@localhost:5432/chb_portal")
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT count(*) FROM intake_definitions"))
        print(f"Rows in intake_definitions: {res.scalar()}")
        
        res = await conn.execute(text("SELECT count(*) FROM courses"))
        print(f"Rows in courses: {res.scalar()}")
        
        res = await conn.execute(text("SELECT count(*) FROM branches"))
        print(f"Rows in branches: {res.scalar()}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_data())
