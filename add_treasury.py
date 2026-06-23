import asyncio
import os
import sys

# Ensure backend root is in PYTHONPATH
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User, RoleEnum

async def seed_treasury():
    engine = create_async_engine(settings.ASYNC_DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Check if exists
        result = await session.execute(select(User).filter_by(email="treasury@example.com"))
        existing = result.scalars().first()
        if existing:
            print("Treasury user already exists.")
            return

        # Base password
        password = "password123"
        hashed_pw = get_password_hash(password)

        treasury_user = User(
            email="treasury@example.com",
            hashed_password=hashed_pw,
            role=RoleEnum.TREASURY,
            full_name="Treasury Officer",
            phone_number="1234567895",
            is_active=True
        )

        session.add(treasury_user)
        await session.commit()
        print("Successfully created treasury stakeholder.")

if __name__ == "__main__":
    asyncio.run(seed_treasury())
