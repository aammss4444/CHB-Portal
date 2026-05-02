
import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.institution import Institution

async def check_institutions():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Institution))
        institutions = result.scalars().all()
        print(f"Found {len(institutions)} institutions:")
        for inst in institutions:
            print(f"ID: {inst.id}, Name: {inst.name}, Code: {inst.code}")

if __name__ == "__main__":
    asyncio.run(check_institutions())
