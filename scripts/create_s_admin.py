import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import AsyncSessionLocal
from app.models.user import User, RoleEnum
from app.core.security import get_password_hash

async def create_admin():
    async with AsyncSessionLocal() as db:
        hashed_password = get_password_hash("1234")
        admin = User(
            email="s.admin@gmail.com",
            hashed_password=hashed_password,
            role=RoleEnum.ADMIN,
            full_name="System Admin",
            is_active=True
        )
        db.add(admin)
        await db.commit()
        print("Admin user s.admin@gmail.com created successfully.")

if __name__ == "__main__":
    asyncio.run(create_admin())
