
import asyncio
import os
import json
import logging
from uuid import UUID

# Mock settings
class MockSettings:
    ENABLE_LLM = True
    LLM_PROVIDER = "openai"
    OPENAI_MODEL = "gpt-4o-mini"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    LLM_TIMEOUT_SECONDS = 30
    OLLAMA_BASE_URL = ""
    DEBUG = True

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

# Patch settings
import app.core.config
app.core.config.settings = MockSettings()

from app.modules.vacancy.ai_engine import VacancyAIEngine

logging.basicConfig(level=logging.INFO)

async def smoke_test_step2():
    print("--- STEP 2 VACANCY AI SMOKE TEST ---")
    engine = VacancyAIEngine()
    
    # Scenario: Branch needs 10 faculty, has 7, but 3 are deputed (high reliance)
    test_data = {
        "branch_name": "Computer Science",
        "required_faculty": 10,
        "existing_faculty_count": 7,
        "suggested_vacancy": 3
    }
    
    faculty_list = [
        {"designation": "Assistant Professor", "specialization": "Mathematics", "employment_type": "PERMANENT"}, # Mismatch?
        {"designation": "Assistant Professor", "specialization": "Physics", "employment_type": "PERMANENT"}, # Mismatch?
        {"designation": "Assistant Professor", "specialization": "AI", "employment_type": "PERMANENT"},
        {"designation": "Assistant Professor", "specialization": "OS", "employment_type": "PERMANENT"},
        {"designation": "Assistant Professor", "specialization": "Network", "employment_type": "DEPUTED_IN"},
        {"designation": "Assistant Professor", "specialization": "Database", "employment_type": "DEPUTED_IN"},
        {"designation": "Assistant Professor", "specialization": "Web", "employment_type": "DEPUTED_IN"}
    ]
    
    history = {"previous_vacancy": 2}

    print(f"\n[Scenario: Workload Imbalance & Deputation Reliance]")
    print(f"Inputs: Required=10, Existing=7 (3 Deputed), Branch=CS")
    
    try:
        result = await engine.analyze_vacancy(test_data, faculty_list, history)
        
        print("\n--- AI VACANCY ANALYSIS RESULT ---")
        print(f"AI Suggested Vacancy: {result.get('ai_suggested_vacancy')}")
        print(f"Justification: {result.get('justification')}")
        print(f"Overloaded: {result.get('overloaded')}")
        print(f"Underutilized: {result.get('underutilized')}")
        print(f"Insights: {result.get('insights')}")
        print(f"Confidence: {result.get('confidence_score')}")

        if result.get("ai_suggested_vacancy") >= 3:
            print("\nSUCCESS: AI provided vacancy suggestion.")
        else:
            print("\nWARNING: AI suggestion seems low given the context.")

    except Exception as e:
        print(f"\nFAIL: Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(smoke_test_step2())
