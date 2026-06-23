import asyncio
import json
from sqlalchemy import select
from app.db.session import async_sessionmaker, engine
from app.models.user import User
from app.core.security import create_access_token
from app.modules.billing.controller import BillingController

import requests

async def run():
    async with async_sessionmaker(engine)() as session:
        user = await session.scalar(select(User).filter(User.email=='principal@gpp.edu.in'))
        token = create_access_token(user.id)
        
    res = requests.get("http://127.0.0.1:8080/api/billing/bills/summary?institution_id=12", headers={"Authorization": f"Bearer {token}"})
    print(res.status_code)
    print(res.text)

if __name__ == "__main__":
    asyncio.run(run())
