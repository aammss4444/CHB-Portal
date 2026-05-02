import asyncio
from sqlalchemy import delete
from app.db.session import AsyncSessionLocal
from app.models.advertisement import Advertisement
from app.models.advertisement_audit import AdvertisementAudit
from app.models.published_advertisement import PublishedAdvertisement
from app.models.application import Application

async def run():
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Application))
        await db.execute(delete(PublishedAdvertisement))
        await db.execute(delete(AdvertisementAudit))
        await db.execute(delete(Advertisement))
        await db.commit()

asyncio.run(run())
