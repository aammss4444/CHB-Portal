import asyncio
from app.db.session import engine
from sqlalchemy import text

async def add_column():
    async with engine.begin() as conn:
        await conn.execute(text('ALTER TABLE faculty_credentials ADD COLUMN IF NOT EXISTS temp_password_plain VARCHAR;'))
        print("Column 'temp_password_plain' added successfully to 'faculty_credentials' table.")

if __name__ == "__main__":
    asyncio.run(add_column())
