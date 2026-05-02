
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check_schema():
    engine = create_async_engine("postgresql+asyncpg://postgres:Amey%40p4444@localhost:5432/chb_portal")
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'courses'
        """))
        columns = result.fetchall()
        print("Columns in courses:")
        for col in columns:
            print(f" - {col[0]} ({col[1]})")
            
        result = await conn.execute(text("SELECT * FROM information_schema.tables WHERE table_name = 'branches'"))
        if result.fetchone():
            print("Table 'branches' still exists.")
        else:
            print("Table 'branches' does not exist.")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_schema())
