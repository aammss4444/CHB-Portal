import asyncio
from sqlalchemy import text
from app.db.session import engine
import sys
import os

# Add the backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), "backend"))

async def check_tables():
    required_tables = [
        "appointment_letters",
        "appointment_templates",
        "selection_results",
        "advertisements",
        "candidates",
        "applications"
    ]
    
    async with engine.connect() as conn:
        print("Checking for required tables in the database...")
        for table in required_tables:
            result = await conn.execute(text(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table}')"))
            exists = result.scalar()
            status = "EXISTS" if exists else "MISSING"
            print(f"- {table:25} : {status}")
            
        # Check template counts
        if "appointment_templates" in required_tables:
            result = await conn.execute(text("SELECT language, count(*) FROM appointment_templates WHERE is_active = true GROUP BY language"))
            templates = result.all()
            print("\nActive Templates:")
            for lang, count in templates:
                print(f"- {lang}: {count} templates")
            if not templates:
                print("- No active templates found!")

if __name__ == "__main__":
    asyncio.run(check_tables())
