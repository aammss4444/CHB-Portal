import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.user import User

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).filter(User.role == 'ADMIN'))
        admin = result.scalars().first()
        if admin:
            print(f"Admin Email: {admin.email}")
        else:
            print("No admin found")

if __name__ == "__main__":
    asyncio.run(main())
