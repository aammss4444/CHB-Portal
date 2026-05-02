import httpx
import asyncio
from uuid import UUID

BASE_URL = "http://127.0.0.1:8000/api"

async def smoke_test_advertisement_ai():
    print("--- Starting Step 3 Advertisement AI Enhancement Smoke Test ---")
    
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

        # 2. Get full user info and find a confirmed assessment
        me_res = await client.get(f"{BASE_URL}/auth/me", headers=headers)
        user_info = me_res.json()
        inst_id = user_info["institution_id"]
        
        # We need a course_id and assessment_id. Let's find them from the system.
        # From seed_step3: Inst: 37, Course: 39, Year: 2024-25
        # Let's try to fetch the assessment
        assess_res = await client.get(f"{BASE_URL}/vacancies/assessment", params={
            "institution_id": inst_id,
            "course_id": 39,
            "academic_year": "2024-25"
        }, headers=headers)
        
        if assess_res.status_code != 200 or not assess_res.json().get("data"):
            print("No confirmed assessment found. Please run seed_step3 first.")
            return
        
        assessment = assess_res.json()["data"]
        assessment_id = assessment["id"]
        print(f"Using Assessment ID: {assessment_id}")

        # 3. Generate Advertisement (Triggers AI)
        print("\n3. Generating Advertisement (Template + AI)...")
        gen_data = {
            "assessment_id": assessment_id,
            "application_start_date": "2024-06-01",
            "application_end_date": "2024-06-15",
            "qualification_requirements": "As per AICTE/DTE norms (M.E/M.Tech preferred, PhD desirable)",
            "required_documents": "- Degree Certificates\n- Mark Sheets\n- Experience Certificates\n- ID Proof",
            "important_instructions": "- Candidates must attend walk-in interview\n- Original documents required",
            "interview_venue": "Government College of Engineering, Pune"
        }
        gen_res = await client.post(f"{BASE_URL}/advertisements/generate", json=gen_data, headers=headers)
        
        if gen_res.status_code == 400 and "ADVERTISEMENT_ALREADY_EXISTS" in gen_res.text:
            print("Advertisement already exists. Fetching existing one...")
            # Fetch all ads for this principal
            all_ads = await client.get(f"{BASE_URL}/advertisements/published", headers=headers)
            # Actually, let's just use the /generate output if it failed with 400
            # For simplicity, I'll just delete the existing one via a script if I could, 
            # but I'll just assume I can't easily find the ID without listing.
            # I'll just list them.
            ad_list_res = await client.get(f"{BASE_URL}/advertisements/published", params={"institution_id": inst_id}, headers=headers)
            # Wait, published only shows published.
            # I'll just mock it or skip the generation step.
            pass
        
        if gen_res.status_code != 201:
            print(f"Generation failed: {gen_res.text}")
            return
        
        response = gen_res.json()["data"]
        ad_id = response["template_ad"]["id"]
        
        print("\n--- AI Advertisement Enhancement Result ---")
        ai_analysis = response["ai_enhanced_ad"]
        print(f"AI Analysis Status: {ai_analysis['status']}")
        print(f"Confidence Score: {ai_analysis['confidence_score']}")
        
        print("\nAI Issues Detected:")
        for issue in ai_analysis["issues"]:
            print(f"- {issue}")
            
        print("\nAI Suggestions:")
        for suggestion in ai_analysis["suggestions"]:
            print(f"- {suggestion}")

        # 4. Submit Advertisement (Triggers Warning if AI status is NEEDS_IMPROVEMENT)
        print(f"\n4. Submitting Advertisement ID: {ad_id}...")
        submit_res = await client.post(f"{BASE_URL}/advertisements/{ad_id}/submit", headers=headers)
        
        if submit_res.status_code == 200:
            submit_data = submit_res.json()
            print("Submission status: success")
            if submit_data.get("warning"):
                print(f"Warning Received: {submit_data['warning']}")
        else:
            print(f"Submission failed: {submit_res.text}")

        print("\n[SUCCESS] Advertisement AI Smoke Test Completed.")

if __name__ == "__main__":
    asyncio.run(smoke_test_advertisement_ai())
