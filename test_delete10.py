import asyncio
from app.db.session import AsyncSessionLocal
from app.api.requirements import delete_institution
from app.models.user import User

async def main():
    async with AsyncSessionLocal() as session:
        # Mock current_user
        mock_user = User(id=1, role='ADMIN')
        try:
            result = await delete_institution(institution_id=5, db=session, current_user=mock_user)
            print(result)
        except Exception as e:
            print(f"Exception raised: {e}")

if __name__ == "__main__":
    asyncio.run(main())
