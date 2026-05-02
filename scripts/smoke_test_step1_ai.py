import httpx
import asyncio
import sys

BASE_URL = "http://127.0.0.1:8000/api"

async def smoke_test_ai_validation():
    print("--- Starting Step 1 AI Validation Smoke Test ---")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Login as Admin
        print("\n1. Logging in as Admin...")
        login_res = await client.post(f"{BASE_URL}/auth/login", data={
            "username": "admin@chb.local",
            "password": "Admin@123"
        })
        if login_res.status_code != 200:
            print(f"Login failed: {login_res.text}")
            return
        
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("Login successful.")

        # 2. Get Institution and Course
        print("\n2. Fetching Institutions...")
        inst_res = await client.get(f"{BASE_URL}/requirements/institutions", headers=headers)
        institutions = inst_res.json()
        if not institutions:
            print("No institutions found. Seeding required.")
            # Seed logic here if needed, but assuming dev env has seeds.
            return
        
        inst_id = institutions[0]["id"]
        course_id = institutions[0]["courses"][0]["id"]
        branch_level = institutions[0]["courses"][0]["level"]
        print(f"Using Inst: {inst_id}, Course: {course_id} ({branch_level})")

        # 3. Define Intake (High growth case)
        print("\n3. Defining Intake (Creating Anomaly Case)...")
        intake_data = {
            "course_id": course_id,
            "academic_year": "2026-2027",
            "approved_seats": 60,
            "actual_admitted": 85 # Overflow anomaly
        }
        intake_res = await client.post(f"{BASE_URL}/requirements/intake", json=intake_data, headers=headers)
        if intake_res.status_code != 200:
            print(f"Intake creation failed: {intake_res.text}")
            return
        intake_id = intake_res.json()["id"]
        print(f"Intake defined. ID: {intake_id}")

        # 4. Generate Requirement
        print("\n4. Generating Faculty Requirement...")
        gen_res = await client.post(f"{BASE_URL}/requirements/generate", json={"intake_id": intake_id}, headers=headers)
        if gen_res.status_code != 200:
            print(f"Generation failed: {gen_res.text}")
            return
        req_data = gen_res.json()
        print(f"Requirement Generated. Count: {req_data['computed_required_count']}")

        # 5. Call AI Validation
        print("\n5. Calling AI Validation Endpoint...")
        val_res = await client.post(f"{BASE_URL}/requirements/validate", json={"intake_id": intake_id}, headers=headers)
        if val_res.status_code != 200:
            print(f"Validation failed: {val_res.text}")
            return
        
        response = val_res.json()
        print("\n--- AI Validation Result ---")
        print(f"Status: {response['status']}")
        
        ai_analysis = response["data"]["ai_analysis"]
        print(f"AI Engine Version: {ai_analysis.get('ai_engine_version', 'N/A')}")
        print(f"Confidence Score: {ai_analysis['confidence_score']}")
        
        print("\nDetected AI Anomalies:")
        for anom in ai_analysis["anomalies"]:
            print(f"- [{anom['severity']}] {anom['type']}: {anom['message']}")
            print(f"  Insight: {anom['insight']}")
            print(f"  Rec: {anom['recommendation']}")
            
        print("\nAI Insights:")
        for insight in ai_analysis["insights"]:
            print(f"- {insight}")

        # Verification
        if any(a["type"] == "ADMISSION_OVERFLOW" for a in ai_analysis["anomalies"]):
            print("\n[SUCCESS] Verification Success: AI correctly detected admission overflow.")
        else:
            print("\n[FAILURE] Verification Failed: AI missed admission overflow.")

if __name__ == "__main__":
    asyncio.run(smoke_test_ai_validation())
