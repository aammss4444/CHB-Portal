import asyncio
from sqlalchemy import select, func, text
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.institution import Institution

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
        ))
        tables = result.fetchall()
        for t in tables:
            print(t[0])

if __name__ == "__main__":
    asyncio.run(main())
