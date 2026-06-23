import asyncio
from app.db.session import engine
from sqlalchemy import text

async def check_results():
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT id, candidate_id, status FROM selection_results WHERE advertisement_id = '6636ce13-310a-4e91-97ec-cb60208b1045';"))
        rows = res.fetchall()
        print(f"Results for AD 6636ce13-310a-4e91-97ec-cb60208b1045: {rows}")

if __name__ == "__main__":
    asyncio.run(check_results())
