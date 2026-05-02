
import asyncio
from sqlalchemy import text
from app.db.session import engine, Base
# Import all models to ensure they are registered with Base.metadata
import app.models # This assumes __init__.py imports all models

async def clear_database():
    async with engine.begin() as conn:
        print("Fetching table names...")
        # Get all table names from the database directly to be sure
        result = await conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
        """))
        tables = [row[0] for row in result.fetchall() if row[0] != 'alembic_version']
        
        if not tables:
            print("No tables found to clear.")
            return

        print(f"Truncating tables: {', '.join(tables)}")
        # Use TRUNCATE with CASCADE to handle foreign keys
        truncate_query = f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE;"
        await conn.execute(text(truncate_query))
        print("Database cleared successfully!")

if __name__ == "__main__":
    asyncio.run(clear_database())
