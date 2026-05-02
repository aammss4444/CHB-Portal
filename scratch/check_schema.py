
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check_schema():
    engine = create_async_engine("postgresql+asyncpg://postgres:Amey%40p4444@localhost:5432/chb_portal")
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'intake_definitions'
        """))
        columns = result.fetchall()
        print("Columns in intake_definitions:")
        for col in columns:
            print(f" - {col[0]} ({col[1]})")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_schema())
