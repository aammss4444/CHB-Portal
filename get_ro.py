import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.user import User

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).filter(User.role == 'RO'))
        ro = result.scalars().first()
        if ro:
            print(f"RO Email: {ro.email}")
        else:
            print("No RO found")

if __name__ == "__main__":
    asyncio.run(main())
