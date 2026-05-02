import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

async def drop_audit():
    engine = create_async_engine(settings.ASYNC_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS audit_logs CASCADE"))
        print("Dropped audit_logs")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(drop_audit())
