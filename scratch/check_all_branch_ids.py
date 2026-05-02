
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check_all_branch_ids():
    engine = create_async_engine("postgresql+asyncpg://postgres:Amey%40p4444@localhost:5432/chb_portal")
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT table_name, column_name FROM information_schema.columns WHERE column_name = 'branch_id'"))
        rows = res.fetchall()
        print("Tables with branch_id:")
        for r in rows:
            print(f" - {r[0]}.{r[1]}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_all_branch_ids())
