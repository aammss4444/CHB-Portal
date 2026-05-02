import asyncio
import logging
from app.services.llm_service import LLMService

logging.basicConfig(level=logging.INFO)

async def test_ollama():
    print("--- Testing Ollama Integration (Llama 3.1) ---")
    service = LLMService()
    print(f"Provider: {service.provider}")
    print(f"Enabled: {service.enabled}")
    print(f"Model: {service.model_name}")

    if not service.enabled or service.provider != "ollama":
        print("Error: Ollama is not enabled or configured correctly in .env")
        return

    test_data = {
        "approved_seats": 60,
        "actual_admitted": 85,
        "computed_required_count": 5,
        "norm_ratio": 20.0,
        "branch_level": "UG"
    }

    print("\nSending analysis request to local Llama 3.1...")
    result = await service.analyze_requirement(test_data)
    
    if result:
        print("\n--- Local AI Analysis Result ---")
        print(f"Confidence Score: {result.get('confidence_score')}")
        print("\nAnomalies:")
        for anom in result.get("anomalies", []):
            print(f"- {anom.get('type')}: {anom.get('message')}")
        print("\nInsights:")
        for insight in result.get("insights", []):
            print(f"- {insight}")
    else:
        print("\nAnalysis failed. Check if Ollama is responding.")

if __name__ == "__main__":
    asyncio.run(test_ollama())
