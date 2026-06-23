import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.institution import Institution
from app.models.user import User
from app.api.requirements import delete_institution

async def main():
    async with AsyncSessionLocal() as session:
        # Check what's left
        result = await session.execute(select(Institution))
        insts = result.scalars().all()
        print("Current institutions:")
        for i in insts:
            print(f"  ID: {i.id}, Name: {i.name}")
        
        if not insts:
            print("No institutions to delete!")
            return
            
        target = insts[0]
        print(f"\nDeleting institution ID {target.id}: {target.name}")
        mock_user = User(id=1, role='RO')
        try:
            result = await delete_institution(institution_id=target.id, db=session, current_user=mock_user)
            print("SUCCESS:", result)
        except Exception as e:
            print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(main())
