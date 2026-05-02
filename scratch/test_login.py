"""Quick script to debug candidate login issue."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.user import User, RoleEnum
from app.core.security import verify_password, get_password_hash

async def main():
    async with AsyncSessionLocal() as db:
        # 1. List all users
        result = await db.execute(select(User))
        users = result.scalars().all()
        print(f"\n=== All Users ({len(users)}) ===")
        for u in users:
            print(f"  ID={u.id}, email={u.email}, role={u.role}, is_active={u.is_active}")

        # 2. Check if any CANDIDATE users exist
        result = await db.execute(select(User).filter(User.role == RoleEnum.CANDIDATE))
        candidates = result.scalars().all()
        print(f"\n=== Candidate Users ({len(candidates)}) ===")
        for c in candidates:
            print(f"  ID={c.id}, email={c.email}, is_active={c.is_active}")
            # 3. Test password verification
            test_pw = "password123"
            pw_ok = verify_password(test_pw, c.hashed_password)
            print(f"  Password '{test_pw}' verify => {pw_ok}")
            print(f"  Hashed password (first 30 chars): {c.hashed_password[:30]}...")

        if not candidates:
            print("\n  No candidate users found! Registering a test candidate...")
            hashed = get_password_hash("password123")
            test_user = User(
                email="testcandidate@test.com",
                hashed_password=hashed,
                role=RoleEnum.CANDIDATE,
                full_name="Test Candidate",
                phone_number="9876543210",
                is_active=True,
            )
            db.add(test_user)
            await db.commit()
            print(f"  Created user ID={test_user.id}")
            # Verify it works
            pw_ok = verify_password("password123", test_user.hashed_password)
            print(f"  Password verify => {pw_ok}")

asyncio.run(main())
