import asyncio
import sys
from datetime import date
from decimal import Decimal

# Add project root to path
sys.path.append(".")

from app.db.session import AsyncSessionLocal
from app.models.scoring_weight_config import ScoringWeightConfig
from app.models.user import RoleEnum
from sqlalchemy import select

async def seed_weights():
    async with AsyncSessionLocal() as db:
        # Check if DEFAULT already exists
        stmt = select(ScoringWeightConfig).where(ScoringWeightConfig.config_name == "DEFAULT")
        existing = (await db.execute(stmt)).scalars().first()
        
        if existing:
            print("Default weight config already exists. Skipping.")
            return

        print("Seeding DEFAULT scoring weights...")
        default_config = ScoringWeightConfig(
            config_name="DEFAULT",
            course_id=None,
            level=None,
            advertisement_id=None,
            qualification_weight=Decimal("30.00"),
            experience_weight=Decimal("25.00"),
            interview_weight=Decimal("30.00"),
            publication_weight=Decimal("10.00"),
            reservation_weight=Decimal("5.00"),
            set_by_role=RoleEnum.ADMIN.value,
            effective_from=date(2024, 1, 1),
            is_active=True
        )
        db.add(default_config)
        await db.commit()
        print("Success: Seeded DEFAULT scoring weights (30/25/30/10/5).")

if __name__ == "__main__":
    asyncio.run(seed_weights())
