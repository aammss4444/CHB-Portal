import asyncio
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text, MetaData
from app.core.config import settings

async def clear_db():
    engine = create_async_engine(settings.ASYNC_DATABASE_URL)
    try:
        async with engine.begin() as conn:
            print("Connected to database...")
            
            # We need to run sync code for metadata reflection
            def reflect_metadata(sync_conn):
                meta = MetaData()
                meta.reflect(bind=sync_conn)
                return meta
                
            metadata = await conn.run_sync(reflect_metadata)
            
            tables_to_keep = [
                "institutions",
                "rate_master",
                "scoring_weight_config",
                "norms",
                "academic_calendar",
                "users",
                "alembic_version"
            ]
            
            # Disable triggers for FK
            await conn.execute(text("SET session_replication_role = 'replica';"))
            
            for table in metadata.sorted_tables:
                if table.name not in tables_to_keep:
                    await conn.execute(text(f"DELETE FROM {table.name};"))
                    print(f"Cleared table: {table.name}")
            
            # Delete unwanted users
            res = await conn.execute(text("DELETE FROM users WHERE role NOT IN ('ADMIN', 'RO', 'TREASURY');"))
            print(f"Deleted {res.rowcount} users.")
            
            # Re-enable triggers
            await conn.execute(text("SET session_replication_role = 'origin';"))
            
            print("Selective database clear complete!")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(clear_db())
