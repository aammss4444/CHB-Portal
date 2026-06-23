import asyncio
import os
import sys

# Ensure backend root is in PYTHONPATH
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User, RoleEnum
from app.models.institution import Institution

async def seed_data():
    engine = create_async_engine(settings.ASYNC_DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Create an institution
        institute = Institution(
            name="Government Polytechnic Pune",
            code="GPP-001",
            district="Pune",
            type="Govt"
        )
        session.add(institute)
        await session.commit()
        await session.refresh(institute)

        # Base password
        password = "password123"
        hashed_pw = get_password_hash(password)

        users_to_create = [
            User(
                email="admin@example.com",
                hashed_password=hashed_pw,
                role=RoleEnum.ADMIN,
                full_name="Admin User",
                phone_number="1234567890",
                is_active=True
            ),
            User(
                email="ro@example.com",
                hashed_password=hashed_pw,
                role=RoleEnum.RO,
                full_name="Regional Officer",
                phone_number="1234567891",
                is_active=True
            ),
            User(
                email="candidate@example.com",
                hashed_password=hashed_pw,
                role=RoleEnum.CANDIDATE,
                full_name="Candidate User",
                phone_number="1234567892",
                is_active=True
            ),
            User(
                email="faculty@example.com",
                hashed_password=hashed_pw,
                role=RoleEnum.FACULTY,
                full_name="Faculty User",
                phone_number="1234567893",
                is_active=True
            ),
            User(
                email="principal@gpp.edu.in",
                hashed_password=hashed_pw,
                role=RoleEnum.PRINCIPAL,
                full_name="Principal GPP",
                phone_number="1234567894",
                is_active=True,
                institution_id=institute.id
            )
        ]

        session.add_all(users_to_create)
        await session.commit()

        print("Successfully created stakeholders.")
        print("-" * 30)
        print("Institution created:")
        print(f"Name: {institute.name}")
        print(f"Code: {institute.code}")
        print("-" * 30)
        print("Login Credentials:")
        for u in users_to_create:
            print(f"Role: {u.role.value}")
            print(f"Email: {u.email}")
            print(f"Password: {password}")
            if u.role == RoleEnum.PRINCIPAL:
                print(f"Linked Institution ID: {u.institution_id}")
            print("-" * 30)

if __name__ == "__main__":
    asyncio.run(seed_data())
