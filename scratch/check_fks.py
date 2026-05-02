
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check_fks():
    engine = create_async_engine("postgresql+asyncpg://postgres:Amey%40p4444@localhost:5432/chb_portal")
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT
                tc.table_name, 
                kcu.column_name, 
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name 
            FROM 
                information_schema.table_constraints AS tc 
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = 'intake_definitions';
        """))
        fks = result.fetchall()
        print("Foreign Keys in intake_definitions:")
        for fk in fks:
            print(f" - {fk[1]} -> {fk[2]}({fk[3]})")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_fks())
