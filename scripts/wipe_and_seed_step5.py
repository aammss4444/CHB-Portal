import asyncio
import os
import sys
from datetime import date, timedelta, datetime
from uuid import UUID

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, select
from app.db.session import engine, Base, AsyncSessionLocal
import app.models # Ensure all models are loaded into Base.metadata
from app.models.user import User, RoleEnum
from app.models.institution import Institution, Course
from app.models.norm import Norm
from app.models.intake import IntakeDefinition
from app.models.faculty_req import FacultyRequirement
from app.models.vacancy_assessment import VacancyAssessment
from app.models.advertisement_template import AdvertisementTemplate
from app.models.advertisement import Advertisement
from app.models.scoring_weight_config import ScoringWeightConfig
from app.models.candidate import Candidate
from app.models.candidate_qualification import CandidateQualification
from app.models.application import Application

# API Client simulation (using service layer directly to avoid HTTP overhead and potential server not running)
from app.modules.selection.service import SelectionService
from app.modules.selection.schemas import ShortlistRequest, InterviewMarksRequest
from app.models.user import User, RoleEnum
from app.core.security import get_password_hash

async def recreate_db():
    print("--- Dropping all tables ---")
    async with engine.begin() as conn:
        # Using a raw SQL approach for Postgres drop to be absolutely sure
        await conn.execute(text("DROP SCHEMA public CASCADE;"))
        await conn.execute(text("CREATE SCHEMA public;"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
        
        print("--- Creating all tables ---")
        await conn.run_sync(Base.metadata.create_all)
    print("Database recreated.")

async def seed_data():
    print("--- Seeding Data ---")
    async with AsyncSessionLocal() as db:
        # 1. Users
        admin_pass = get_password_hash("1234")
        admin = User(email="admin@test.com", hashed_password=admin_pass, role=RoleEnum.ADMIN, full_name="Admin User", is_active=True)
        principal = User(email="principal@test.com", hashed_password=admin_pass, role=RoleEnum.PRINCIPAL, full_name="Principal User", is_active=True)
        db.add(admin)
        db.add(principal)
        await db.flush()

        # 2. Institution & Course
        inst = Institution(name="Government College of Engineering, Yavatmal", code="GCOEY", district="Yavatmal", type="GOVT")
        db.add(inst)
        await db.flush()
        
        principal.institution_id = inst.id
        
        course = Course(institution_id=inst.id, name="Computer Science & Engineering", level="UG")
        db.add(course)
        await db.flush()

        # 3. Norms & Intake
        norm = Norm(
            institution_id=inst.id,
            course_id=course.id,
            academic_year="2026-27",
            faculty_student_ratio=20.0,
            norm_type="COURSE_WISE",
            course_category="Engineering (Degree - B.E./B.Tech)",
            min_qualification="M.E./M.Tech in relevant course",
            grade_requirement="First Class",
            max_age=38,
            workload_hours_per_week=18,
        )
        db.add(norm)
        intake = IntakeDefinition(course_id=course.id, academic_year="2026-27", approved_seats=60, actual_admitted=60)
        db.add(intake)
        await db.flush()

        # 4. Requirement & Vacancy
        req = FacultyRequirement(intake_id=intake.id, computed_required_count=3, formula_breakdown={"seats": 60, "ratio": 20})
        db.add(req)
        await db.flush()
        assessment = VacancyAssessment(
            institution_id=inst.id, course_id=course.id, academic_year="2026-27", 
            requirement_id=req.id,
            required_count=3, total_existing=0, effective_existing=0,
            suggested_vacancy=3, status="AI_SUGGESTED"
        )
        db.add(assessment)
        await db.flush()

        # 5. Advertisement
        # Need templates
        db.add(AdvertisementTemplate(name="STANDARD_EN", language="EN", template_body="Ad body", is_active=True, created_by=admin.id))
        db.add(AdvertisementTemplate(name="STANDARD_MR", language="MR", template_body="जाहिरात", is_active=True, created_by=admin.id))
        await db.flush()

        ad = Advertisement(
            assessment_id=assessment.id,
            institution_id=inst.id, course_id=course.id, academic_year="2026-27",
            vacancy_count=3, status="PUBLISHED", 
            content_en="Ad: Computer Science", content_mr="जाहिरात: संगणक शास्त्र",
            application_start_date=date.today() - timedelta(days=5),
            application_end_date=date.today() + timedelta(days=10),
            created_by=principal.id
        )
        db.add(ad)
        await db.flush()

        # 6. Scoring Weights
        weight = ScoringWeightConfig(
            config_name="DEFAULT_WEIGHTS",
            course_id=course.id, level="UG", advertisement_id=ad.id,
            qualification_weight=30, experience_weight=20, interview_weight=30,
            publication_weight=10, reservation_weight=10,
            set_by_role="ADMIN",
            effective_from=date.today(), is_active=True, created_by=admin.id
        )
        db.add(weight)
        await db.flush()

        # 7. Candidates & Applications
        cand_pass = get_password_hash("1234")
        candidates = []
        for i in range(1, 6):
            c_user = User(email=f"candidate{i}@test.com", hashed_password=cand_pass, role=RoleEnum.CANDIDATE, full_name=f"Candidate {i}", is_active=True)
            db.add(c_user)
            await db.flush()
            
            c = Candidate(user_id=c_user.id, full_name=f"Candidate {i}", category="OPEN", mobile=f"900000000{i}", email=f"candidate{i}@test.com")
            db.add(c)
            await db.flush()
            candidates.append(c)
            
            # Qualification
            q = CandidateQualification(candidate_id=c.id, degree="ME" if i < 3 else "BE", specialization="CS", year_of_passing=2020, percentage=80, is_highest=True)
            db.add(q)
            
            # Application
            app = Application(
                advertisement_id=ad.id, candidate_id=c.id, 
                institution_id=inst.id, course_id=course.id, academic_year="2026-27",
                application_number=f"APP-{ad.id.hex[:4]}-{i}",
                applied_designation="Assistant Professor", 
                status="SUBMITTED", submitted_at=datetime.utcnow()
            )
            db.add(app)
            await db.flush()

        await db.commit()
        print(f"Seed complete. Advertisement ID: {ad.id}")
        
        # 8. Use SelectionService to shortlist
        selection_service = SelectionService()
        
        # Get applications for this ad
        apps = (await db.execute(select(Application).where(Application.advertisement_id == ad.id))).scalars().all()
        app_ids = [a.id for a in apps]
        
        print(f"Shortlisting {len(app_ids)} candidates for Ad {ad.id}")
        await selection_service.shortlist_candidates(db, principal, ad.id, ShortlistRequest(application_ids=app_ids, remarks="Seeded shortlist"))
        
        print("Seeding complete. Use these credentials:")
        print("  Admin: admin@test.com / 1234")
        print("  Principal: principal@test.com / 1234")
        print(f"  Advertisement ID: {ad.id}")

async def main():
    await recreate_db()
    await seed_data()

if __name__ == "__main__":
    asyncio.run(main())
