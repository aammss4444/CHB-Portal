
import asyncio
import os
import json
import logging
from typing import Dict, Any

# Mock settings and logger for standalone test
class MockSettings:
    ENABLE_LLM = True
    LLM_PROVIDER = "openai"
    OPENAI_MODEL = "gpt-4o-mini"
    # Use the key from .env (the user had sk-proj... in GEMINI_API_KEY field but directed OpenAI)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    LLM_TIMEOUT_SECONDS = 30
    OLLAMA_BASE_URL = ""

# Setup environment before importing service
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

# Monkey patch settings before LLMService initialization
import app.core.config
app.core.config.settings = MockSettings()

from app.services.llm_service import LLMService
from app.modules.requirements.ai_engine import RequirementAIEngine

logging.basicConfig(level=logging.INFO)

async def smoke_test():
    print("--- STEP 1 AI SMOKE TEST (OPENAI) ---")
    
    # 1. Initialize Service with Mock Settings
    service = LLMService()
    engine = RequirementAIEngine()
    
    if not service.enabled:
        print("FAIL: LLM Service not enabled")
        return

    print(f"Provider: {service.provider}")
    print(f"Model: {service.model_name}")

    # 2. Prepare Test Data (Admission Overflow Scenario)
    test_data = {
        "intake_id": 101,
        "approved_seats": 60,
        "actual_admitted": 85,  # Overflow!
        "computed_required_count": 5,
        "norm_ratio": 15.0,
        "branch_level": "UG"
    }
    
    test_history = {
        "previous_required_count": 4,
        "previous_actual_admitted": 60
    }

    print("\n[Scenario 1: Admission Overflow & Growth]")
    print(f"Input: {json.dumps(test_data, indent=2)}")
    
    try:
        # We test the engine which orchestrates LLM
        # This will call LLMService.analyze_requirement internally
        result = await engine.analyze_requirement(test_data, test_history)
        
        print("\n--- AI ANALYSIS RESULT ---")
        print(f"Summary: {result['ai_summary']}")
        print(f"Confidence: {result['confidence_score']}")
        print(f"Insights: {result['insights']}")
        print("\nAnomalies Detected:")
        for a in result['anomalies']:
            print(f"- [{a['severity']}] {a['type']}: {a['message']}")
            print(f"  Insight: {a['insight']}")
            print(f"  Rec: {a['recommendation']}")

        # Verification
        has_overflow = any(a['type'] == 'ADMISSION_OVERFLOW' for a in result['anomalies'])
        if has_overflow:
            print("\nSUCCESS: AI correctly identified Admission Overflow.")
        else:
            print("\nWARNING: Admission Overflow anomaly missing.")

    except Exception as e:
        print(f"\nFAIL: Exception during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(smoke_test())
