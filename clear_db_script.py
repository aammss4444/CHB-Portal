import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.core.config import settings

async def clear_db():
    engine = create_async_engine(settings.ASYNC_DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        # Get all tables
        result = await conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ))
        tables = [row[0] for row in result.fetchall()]
        
        # Filter out alembic_version if we want to keep migrations intact
        if 'alembic_version' in tables:
            tables.remove('alembic_version')
            
        if tables:
            tables_str = ", ".join([f'"{t}"' for t in tables])
            print(f"Truncating tables: {tables_str}")
            await conn.execute(text(f"TRUNCATE TABLE {tables_str} CASCADE;"))
            print("Database cleared successfully.")
        else:
            print("No tables found in the public schema.")

if __name__ == "__main__":
    asyncio.run(clear_db())
