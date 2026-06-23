import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        # Login to get admin token
        login_resp = await client.post("http://127.0.0.1:8080/api/auth/login", data={
            "username": "admin@test.com",
            "password": "admin"
        })
        print(f"Login Status: {login_resp.status_code}")
        if login_resp.status_code != 200:
            print(login_resp.text)
            return
            
        data = login_resp.json()
        token = data.get("access_token")
        
        # Now delete institution 4 (IIT Patna)
        headers = {"Authorization": f"Bearer {token}"}
        delete_resp = await client.delete("http://127.0.0.1:8080/api/requirements/institutions/4", headers=headers)
        
        print(f"Delete Status: {delete_resp.status_code}")
        print(f"Delete Response: {delete_resp.text}")

if __name__ == "__main__":
    asyncio.run(main())
