import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.institution import Institution

import traceback

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Institution).filter(Institution.id == 8))
        inst = result.scalars().first()
        if not inst:
            print("Inst 8 not found")
            return
        
        print("Found inst 8. Deleting...")
        try:
            await session.delete(inst)
            await session.commit()
            print("Deleted successfully!")
        except Exception as e:
            print("Exception:")
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
