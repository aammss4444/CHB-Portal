import asyncio
import os
import sys

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.institution import Institution

async def list_institutions():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Institution))
        insts = result.scalars().all()
        for i in insts:
            print(f"{i.id}: {i.name}")

if __name__ == "__main__":
    asyncio.run(list_institutions())
