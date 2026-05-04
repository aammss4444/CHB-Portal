import asyncio
import os
import sys
from sqlalchemy import select, func

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import AsyncSessionLocal
from app.models import Advertisement, ShortlistedCandidate, Application, ScoringWeightConfig

async def check():
    async with AsyncSessionLocal() as db:
        # 1. Check Advertisements
        ads = (await db.execute(select(Advertisement))).scalars().all()
        print(f"Advertisements: {len(ads)}")
        for ad in ads:
            print(f"  - ID: {ad.id}, Status: {ad.status}, Vacancy: {ad.vacancy_count}")

        # 2. Check Shortlisted Candidates
        shortlisted = (await db.execute(select(ShortlistedCandidate))).scalars().all()
        print(f"Shortlisted Candidates: {len(shortlisted)}")
        
        # 3. Check Applications
        apps = (await db.execute(select(Application))).scalars().all()
        print(f"Total Applications: {len(apps)}")

        # 4. Check Scoring Weights
        weights = (await db.execute(select(ScoringWeightConfig))).scalars().all()
        print(f"Scoring Weights: {len(weights)}")
        for w in weights:
            print(f"  - Config: {w.config_name}, Ad ID: {w.advertisement_id}")

if __name__ == "__main__":
    asyncio.run(check())
