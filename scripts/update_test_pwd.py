import asyncio
from app.db.session import engine
from sqlalchemy import text

async def update_test_user():
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE faculty_credentials SET temp_password_plain = 'Welcome@123' WHERE portal_username = 'candidate.1@gcoey.chb';"))
        print("Updated password for test user 'candidate.1@gcoey.chb'")

if __name__ == "__main__":
    asyncio.run(update_test_user())
