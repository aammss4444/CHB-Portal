import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.institution import Institution

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Institution))
        institutions = result.scalars().all()
        print("INSTITUTIONS IN DB:")
        for inst in institutions:
            print(f"- ID: {inst.id}, Name: {inst.name}, Code: {inst.code}")

if __name__ == "__main__":
    asyncio.run(main())
