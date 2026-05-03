import httpx
import asyncio
import sys

BASE_URL = "http://127.0.0.1:8000/api"

async def smoke_test_vacancy_ai():
    print("--- Starting Step 2 Vacancy AI Intelligence Smoke Test ---")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Login as Principal
        print("\n1. Logging in as Principal...")
        login_res = await client.post(f"{BASE_URL}/auth/login", data={
            "username": "principal@chb.local",
            "password": "Principal@123"
        })
        if login_res.status_code != 200:
            print(f"Login failed: {login_res.text}")
            return
        
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("Login successful.")

        # 2. Get full user info including institution_id
        me_res = await client.get(f"{BASE_URL}/auth/me", headers=headers)
        user_info = me_res.json()
        inst_id = user_info["institution_id"]
        
        # Fetch course for this institution
        inst_res = await client.get(f"{BASE_URL}/requirements/institutions")
        institutions = inst_res.json()
        target_inst = next((i for i in institutions if i["id"] == inst_id), None)
        if not target_inst or not target_inst["courses"]:
            print("No course found for Principal's institution.")
            return
        course_id = target_inst["courses"][0]["id"]
        academic_year = "2024-25" # From Step 3 seed
        
        print(f"Using Inst: {inst_id}, Course: {course_id}, Year: {academic_year}")

        # 3. Call Vacancy Suggestion (Triggers AI)
        print("\n3. Calling Vacancy Suggestion Endpoint...")
        suggest_data = {
            "institution_id": inst_id,
            "course_id": course_id,
            "academic_year": academic_year
        }
        suggest_res = await client.post(f"{BASE_URL}/vacancies/suggest", json=suggest_data, headers=headers)
        if suggest_res.status_code != 200:
            print(f"Suggestion failed: {suggest_res.text}")
            return
        
        response = suggest_res.json()
        print("\n--- Vacancy AI Analysis Result ---")
        print(f"System Suggested: {response['data']['system_vacancy']}")
        
        ai_analysis = response["data"]["ai_analysis"]
        print(f"AI Suggested Vacancy: {ai_analysis['ai_suggested_vacancy']}")
        print(f"Confidence Score: {ai_analysis['confidence_score']}")
        
        print("\nDetected AI Anomalies:")
        for anom in ai_analysis["anomalies"]:
            print(f"- [{anom['severity']}] {anom['type']}: {anom['message']}")
            
        print("\nAI Insights:")
        for insight in ai_analysis["insights"]:
            print(f"- {insight}")
            
        print("\nAI Recommendations:")
        for rec in ai_analysis["recommendations"]:
            print(f"- {rec}")

        print("\n[SUCCESS] Vacancy AI Smoke Test Completed.")

if __name__ == "__main__":
    asyncio.run(smoke_test_vacancy_ai())
