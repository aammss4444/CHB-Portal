import asyncio
from sqlalchemy import text
from app.db.session import engine

async def check():
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'advertisements';"))
        for row in result.fetchall():
            print(f"{row[0]}: {row[1]}")

asyncio.run(check())
