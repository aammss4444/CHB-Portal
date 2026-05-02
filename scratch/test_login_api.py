"""Test the login endpoint directly via httpx."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import asyncio
import httpx

async def main():
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Test 1: Login as candidate
        print("=== Test: Login as candidate ===")
        try:
            resp = await client.post(
                "http://localhost:8000/api/auth/login",
                data={"username": "candidate@example.com", "password": "password123"},
            )
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text}")
        except Exception as e:
            print(f"ERROR: {e}")

        # Test 2: Login as admin (for comparison)
        print("\n=== Test: Login as admin ===")
        try:
            resp = await client.post(
                "http://localhost:8000/api/auth/login",
                data={"username": "s.admin@gmail.com", "password": "password123"},
            )
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text}")
        except Exception as e:
            print(f"ERROR: {e}")

asyncio.run(main())
