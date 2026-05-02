
import asyncio
import json
from uuid import UUID
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.candidate import Candidate
from app.models.application import Application, ApplicationStatus
from app.models.advertisement import Advertisement

async def check_db():
    async with AsyncSessionLocal() as db:
        # Check User
        res = await db.execute(select(User).where(User.email == "cand_complete@test.com"))
        user = res.scalars().first()
        if user:
            print(f"User found: ID={user.id}, Email={user.email}")
            res = await db.execute(select(Candidate).where(Candidate.user_id == user.id))
            candidate = res.scalars().first()
            if candidate:
                print(f"Candidate found for user: ID={candidate.id}, Aadhar={candidate.aadhar_number}")
        else:
            print("User cand_complete@test.com not found")

        # Check Aadhar
        aadhar_hash = "2a33349e7e606a8ad2e30e3c84521f9377450cf09083e162e0a9b1480ce0f972"
        res = await db.execute(select(Candidate).where(Candidate.aadhar_number == aadhar_hash))
        cand_by_aadhar = res.scalars().first()
        if cand_by_aadhar:
            print(f"Candidate with Aadhar hash found: ID={cand_by_aadhar.id}, UserID={cand_by_aadhar.user_id}, Email={cand_by_aadhar.email}")
            res = await db.execute(select(User).where(User.id == cand_by_aadhar.user_id))
            user_by_aadhar = res.scalars().first()
            if user_by_aadhar:
                print(f"User for this Aadhar: ID={user_by_aadhar.id}, Email={user_by_aadhar.email}")
        else:
            print("No candidate found with that Aadhar hash")

if __name__ == "__main__":
    asyncio.run(check_db())
