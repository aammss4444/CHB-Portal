import asyncio
import hashlib
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal
from app.models.advertisement import Advertisement, AdvertisementStatus
from app.models.institution import Course
from app.models.user import RoleEnum, User
from app.models.candidate import Candidate
from app.models.application import Application, ApplicationStatus


async def seed_step4() -> None:
    async with AsyncSessionLocal() as db:
        # 1. Get or create a published advertisement
        first_Course = (await db.execute(select(Course).order_by(Course.id.asc()))).scalars().first()
        if not first_Course:
            print("No Course found. Please run Step 3 seed first.")
            return

        institution_id = first_Course.institution_id
        course_id = first_Course.id
        academic_year = "2024-25"

        ad = (
            await db.execute(
                select(Advertisement).where(
                    Advertisement.institution_id == institution_id,
                    Advertisement.course_id == course_id,
                    Advertisement.academic_year == academic_year,
                    Advertisement.status == AdvertisementStatus.PUBLISHED.value,
                )
            )
        ).scalars().first()

        if not ad:
            # Create a published ad if not exists
            ad = Advertisement(
                institution_id=institution_id,
                course_id=course_id,
                academic_year=academic_year,
                status=AdvertisementStatus.PUBLISHED.value,
                application_start_date=date.today() - timedelta(days=5),
                application_end_date=date.today() + timedelta(days=10),
                content_en="Sample Ad Content EN",
                content_mr="Sample Ad Content MR",
                public_token="test-public-token",
            )
            db.add(ad)
            await db.flush()
            print(f"Created published advertisement: {ad.id}")

        # 2. Create Candidate Users
        # User 1: Incomplete Profile
        cand1_email = "cand_incomplete@test.com"
        user1 = (await db.execute(select(User).where(User.email == cand1_email))).scalars().first()
        if not user1:
            user1 = User(
                email=cand1_email,
                hashed_password=get_password_hash("Candidate@123"),
                role=RoleEnum.CANDIDATE,
                full_name="Candidate Incomplete",
            )
            db.add(user1)
            await db.flush()
            
            candidate1 = Candidate(
                user_id=user1.id,
                full_name="Candidate Incomplete",
                date_of_birth=date(1995, 5, 20),
                mobile="9876543210",
                email=cand1_email,
                is_profile_complete=False # Missing some fields
            )
            db.add(candidate1)
            print("Created candidate with incomplete profile.")

        # User 2: Complete Profile
        cand2_email = "cand_complete@test.com"
        user2 = (await db.execute(select(User).where(User.email == cand2_email))).scalars().first()
        if not user2:
            user2 = User(
                email=cand2_email,
                hashed_password=get_password_hash("Candidate@123"),
                role=RoleEnum.CANDIDATE,
                full_name="Candidate Complete",
            )
            db.add(user2)
            await db.flush()

            candidate2 = Candidate(
                user_id=user2.id,
                full_name="Candidate Complete",
                father_name="Senior Test",
                date_of_birth=date(1990, 1, 1),
                gender="MALE",
                category="OPEN",
                religion="Test",
                nationality="Indian",
                mobile="9999988888",
                email=cand2_email,
                address="123 Test Street",
                district="Pune",
                state="Maharashtra",
                pincode="411001",
                aadhar_number=hashlib.sha256("987654321098".encode()).hexdigest(),
                is_profile_complete=True
            )
            db.add(candidate2)
            await db.flush()
            print("Created candidate with complete profile.")

            # Create an application for this candidate
            import random
            app_num = f"APP-{random.randint(10000, 99999)}"
            app = Application(
                candidate_id=candidate2.id,
                advertisement_id=ad.id,
                institution_id=institution_id,
                course_id=course_id,
                academic_year=academic_year,
                application_number=app_num,
                status=ApplicationStatus.DRAFT.value,
                applied_designation="Assistant Professor",
                declaration_accepted=True
            )
            db.add(app)
            print(f"Created DRAFT application for candidate: {app.id}")

        await db.commit()
        print("Step 4 seed complete.")
        print(f"Incomplete Candidate: {cand1_email} / Candidate@123")
        print(f"Complete Candidate: {cand2_email} / Candidate@123")


if __name__ == "__main__":
    asyncio.run(seed_step4())
