import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app.db.session import AsyncSessionLocal
from app.models.chb_bill import CHBBill, BillApproverRole
from sqlalchemy import select, update

async def fix_bills():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            update(CHBBill)
            .where(CHBBill.current_approver_role == BillApproverRole.DIRECTORATE.value)
            .values(current_approver_role=BillApproverRole.TREASURY.value)
        )
        await session.commit()
        print(f"Updated stuck bills to TREASURY")

if __name__ == "__main__":
    asyncio.run(fix_bills())
