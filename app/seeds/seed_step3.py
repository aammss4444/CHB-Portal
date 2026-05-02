import asyncio
from datetime import datetime

from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal
from app.models.advertisement_template import AdvertisementTemplate
from app.models.institution import Course
from app.models.user import RoleEnum, User
from app.models.vacancy_assessment import VacancyAssessment


ACADEMIC_YEAR = "2024-25"


EN_TEMPLATE = """Advertisement for CHB faculty positions
Institution: {{institution_name}}
Course: {{course_name}}
Vacancies: {{vacancy_count}}
Academic Year: {{academic_year}}
Designation: {{designation}}
Qualification: {{qualification}}
Last Date to Apply: {{application_deadline}}
"""

MR_TEMPLATE = """सीएचबी जाहिरात
संस्था: {{institution_name}}
शाखा: {{course_name}}
रिक्त पदे: {{vacancy_count}}
शैक्षणिक वर्ष: {{academic_year}}
पदनाम: {{designation}}
पात्रता: {{qualification}}
अर्जाची अंतिम तारीख: {{application_deadline}}
"""


async def seed_step3() -> None:
    async with AsyncSessionLocal() as db:
        first_Course = (await db.execute(select(Course).order_by(Course.id.asc()))).scalars().first()
        if not first_Course:
            raise RuntimeError("No Course found. Seed institutions/courses before Step 3.")

        institution_id = first_Course.institution_id
        course_id = first_Course.id

        admin = (await db.execute(select(User).where(User.email == "admin@chb.local"))).scalars().first()
        if not admin:
            admin = User(
                email="admin@chb.local",
                hashed_password=get_password_hash("Admin@123"),
                role=RoleEnum.ADMIN,
                full_name="CHB Admin",
            )
            db.add(admin)

        principal = (await db.execute(select(User).where(User.email == "principal@chb.local"))).scalars().first()
        if not principal:
            principal = User(
                email="principal@chb.local",
                hashed_password=get_password_hash("Principal@123"),
                role=RoleEnum.PRINCIPAL,
                full_name="CHB Principal",
                institution_id=institution_id,
            )
            db.add(principal)
        elif principal.institution_id != institution_id:
            principal.institution_id = institution_id

        await db.flush()

        templates = (
            await db.execute(
                select(AdvertisementTemplate).where(
                    AdvertisementTemplate.name.in_(["CHB_STANDARD_V1_EN", "CHB_STANDARD_V1_MR"])
                )
            )
        ).scalars().all()
        by_name = {tpl.name: tpl for tpl in templates}

        if "CHB_STANDARD_V1_EN" not in by_name:
            db.add(
                AdvertisementTemplate(
                    name="CHB_STANDARD_V1_EN",
                    language="EN",
                    template_body=EN_TEMPLATE,
                    is_active=True,
                    created_by=admin.id,
                )
            )

        if "CHB_STANDARD_V1_MR" not in by_name:
            db.add(
                AdvertisementTemplate(
                    name="CHB_STANDARD_V1_MR",
                    language="MR",
                    template_body=MR_TEMPLATE,
                    is_active=True,
                    created_by=admin.id,
                )
            )

        assessment = (
            await db.execute(
                select(VacancyAssessment).where(
                    VacancyAssessment.institution_id == institution_id,
                    VacancyAssessment.course_id == course_id,
                    VacancyAssessment.academic_year == ACADEMIC_YEAR,
                )
            )
        ).scalars().first()

        if not assessment:
            db.add(
                VacancyAssessment(
                    institution_id=institution_id,
                    course_id=course_id,
                    academic_year=ACADEMIC_YEAR,
                    requirement_id=None,
                    required_count=10,
                    total_existing=7,
                    effective_existing=6,
                    suggested_vacancy=4,
                    confirmed_vacancy=4,
                    status="CONFIRMED",
                    confirmed_by=principal.id,
                    confirmed_at=datetime.utcnow(),
                )
            )
        else:
            assessment.status = "CONFIRMED"
            if assessment.confirmed_vacancy is None:
                assessment.confirmed_vacancy = assessment.suggested_vacancy
            assessment.confirmed_by = principal.id
            assessment.confirmed_at = datetime.utcnow()

        await db.commit()
        print("Step 3 seed complete.")
        print("Admin user: admin@chb.local / Admin@123")
        print("Principal user: principal@chb.local / Principal@123")
        print(f"Institution ID: {institution_id}, Course ID: {course_id}, Academic Year: {ACADEMIC_YEAR}")


if __name__ == "__main__":
    asyncio.run(seed_step3())
