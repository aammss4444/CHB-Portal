import asyncio
import os
import sys

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.user import User

async def list_users():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()
        print(f"{'Email':<30} | {'Role':<10} | {'Inst ID':<10}")
        print("-" * 55)
        for u in users:
            print(f"{u.email:<30} | {u.role:<10} | {str(u.institution_id):<10}")

if __name__ == "__main__":
    asyncio.run(list_users())
