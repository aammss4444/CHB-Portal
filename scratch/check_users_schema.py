
import asyncio
from sqlalchemy import text
from app.db.session import engine

async def check_users_schema():
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name IN ('phone_number', 'is_active', 'force_password_change');
        """))
        columns = result.fetchall()
        print("Columns found in 'users' table:")
        for col in columns:
            print(f"- {col[0]}")

if __name__ == "__main__":
    asyncio.run(check_users_schema())
