import asyncio
import os
import sys

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.advertisement import Advertisement

async def list_ads():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Advertisement))
        ads = result.scalars().all()
        print(f"{'ID':<40} | {'Inst ID':<10} | {'Status':<15}")
        print("-" * 70)
        for a in ads:
            print(f"{str(a.id):<40} | {a.institution_id:<10} | {a.status:<15}")

if __name__ == "__main__":
    asyncio.run(list_ads())
