import httpx
import asyncio
import os
from uuid import UUID

BASE_URL = "http://127.0.0.1:8000/api"

async def smoke_test_step4_ai():
    print("--- Starting Step 4 AI Document Intelligence Smoke Test ---")
    
    async with httpx.AsyncClient(timeout=600.0) as client:
        # 1. Login as Candidate
        print("\n1. Logging in as Candidate...")
        login_res = await client.post(f"{BASE_URL}/auth/login", data={
            "username": "cand_complete@test.com",
            "password": "Candidate@123"
        })
        if login_res.status_code != 200:
            print(f"Login failed: {login_res.text}")
            return
        
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("Login successful.")

        # 2. Get my applications to find a DRAFT one
        apps_res = await client.get(f"{BASE_URL}/applications/my", headers=headers)
        apps = apps_res.json()["data"]
        
        if not apps:
            print("No applications found for candidate. Please run seed_step4 if it exists.")
            return
            
        app_id = apps[0]["application_id"]
        print(f"Using Application ID: {app_id}")

        # 3. Upload a document (Trigger AI)
        print(f"\n3. Uploading 'degree_certificate' (Simulated OCR)...")
        # Create a dummy file
        with open("test_degree.jpg", "w") as f:
            f.write("This is a dummy degree certificate file for testing.")
            
        files = {"file": ("test_degree.jpg", open("test_degree.jpg", "rb"), "image/jpeg")}
        data = {"document_type": "DEGREE_CERTIFICATE"}
        
        upload_res = await client.post(
            f"{BASE_URL}/applications/{app_id}/documents",
            data=data,
            files=files,
            headers=headers
        )
        
        # Cleanup dummy file
        files["file"][1].close()
        os.remove("test_degree.jpg")
        
        if upload_res.status_code != 200:
            print(f"Upload failed: {upload_res.text}")
            return
            
        result = upload_res.json()
        print("\n--- AI Document Analysis Result ---")
        ai_analysis = result.get("ai_analysis", {})
        print(f"Classification Status: {ai_analysis.get('status')}")
        print(f"Confidence Score: {ai_analysis.get('confidence_score')}")
        
        print("\nScrutiny Summary:")
        print(ai_analysis.get("scrutiny_summary"))
        
        print("\nMismatches detected:")
        for mismatch in ai_analysis.get("mismatches", []):
            print(f"- {mismatch}")

        # 4. Fetch AI Summary as Principal (Verify RBAC)
        print("\n4. Fetching AI Summary as Principal...")
        # Login as Principal
        p_login_res = await client.post(f"{BASE_URL}/auth/login", data={
            "username": "principal@chb.local",
            "password": "Principal@123"
        })
        p_token = p_login_res.json()["access_token"]
        p_headers = {"Authorization": f"Bearer {p_token}"}
        
        summary_res = await client.get(f"{BASE_URL}/applications/{app_id}/ai-summary", headers=p_headers)
        if summary_res.status_code == 200:
            print("Successfully fetched AI summary as Principal.")
            print(summary_res.json()["data"]["scrutiny_summary"])
        else:
            print(f"Failed to fetch summary: {summary_res.text}")

        print("\n[SUCCESS] Step 4 AI Document Intelligence Smoke Test Completed.")

if __name__ == "__main__":
    asyncio.run(smoke_test_step4_ai())
