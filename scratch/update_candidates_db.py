
import asyncio
from sqlalchemy import text
from app.db.session import engine

async def update_db():
    async with engine.begin() as conn:
        print("Making date_of_birth nullable in candidates table...")
        await conn.execute(text("ALTER TABLE candidates ALTER COLUMN date_of_birth DROP NOT NULL"))
        print("Database updated successfully!")

if __name__ == "__main__":
    asyncio.run(update_db())
