import asyncio
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.session import AsyncSessionLocal
from app.models.norm import Norm
from sqlalchemy.exc import IntegrityError

async def test_insert():
    async with AsyncSessionLocal() as db:
        try:
            norm = Norm(
                academic_year="2025-2026",
                course_level="UG",
                category="student_faculty_ratio",
                faculty_student_ratio=60.0,
                min_qualification="Phd in Science",
                max_daily_lectures=6,
                credit_to_hour_ratio=1.0
            )
            db.add(norm)
            await db.commit()
            print("Success! Inserted norm ID:", norm.id)
        except IntegrityError as e:
            print("INTEGRITY ERROR DETECTED:")
            print(str(e.orig))
            print("\nDetails:")
            print(e.params)
        except Exception as e:
            print("OTHER ERROR:", e)

asyncio.run(test_insert())
