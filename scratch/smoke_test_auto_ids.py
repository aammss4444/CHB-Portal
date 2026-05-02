import asyncio
import sys
from datetime import datetime, timezone

from app.db.session import AsyncSessionLocal
from app.models.institution import Branch, Institution
from app.models.norm import Norm


async def run() -> int:
    async with AsyncSessionLocal() as db:
        tx = await db.begin()
        try:
            seed = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            inst_code = f"SMOKE-AUTOID-{seed}"

            inst = Institution(
                name="Smoke Test Institute",
                code=inst_code,
                district="Pune",
                type="GOVERNMENT",
            )
            db.add(inst)
            await db.flush()

            branch = Branch(
                institution_id=inst.id,
                name="Smoke Branch",
                level="UG",
            )
            db.add(branch)
            await db.flush()

            norm = Norm(
                academic_year="2026-2027",
                course_level="UG",
                category="student_faculty_ratio",
                faculty_student_ratio=20.0,
                min_qualification="PhD",
                max_daily_lectures=6,
                credit_to_hour_ratio=1.0,
            )
            db.add(norm)
            await db.flush()

            ids = {
                "institution_id": inst.id,
                "branch_id": branch.id,
                "norm_id": norm.id,
            }
            ok = all(isinstance(value, int) and value > 0 for value in ids.values())

            print("SMOKE_TEST:auto_ids")
            for key, value in ids.items():
                print(f"{key}={value}")
            print(f"auto_generated={ok}")

            if not ok:
                return 2
            return 0
        finally:
            await tx.rollback()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
