import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from app.core.config import settings

async def test_query():
    engine = create_async_engine(settings.ASYNC_DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        query = text("""
            SELECT
                (SELECT COUNT(*) FROM advertisements) as ads_count,
                (SELECT COUNT(*) FROM vacancy_assessments) as vacancy_count,
                (SELECT COUNT(*) FROM users) as users_count,
                (SELECT COUNT(*) FROM chb_bill WHERE bill_status = 'TREASURY_PROCESSED') as bills_count
        """)
        result = await session.execute(query)
        row = result.fetchone()
        print("Row:", row)
        print("Ads count:", row.ads_count if row else None)

if __name__ == "__main__":
    asyncio.run(test_query())
