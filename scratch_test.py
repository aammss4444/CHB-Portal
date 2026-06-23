import asyncio
from sqlalchemy import select
from app.db.session import async_sessionmaker, engine
from app.models.user import User

async def run():
    async with async_sessionmaker(engine)() as session:
        user = await session.scalar(select(User).filter(User.email=='principal@gpp.edu.in'))
        print(user.hashed_password if user else 'Not found')

if __name__ == "__main__":
    asyncio.run(run())
