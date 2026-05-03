import httpx
import asyncio
import json
import sys

async def chat():
    print("--- CHB Portal: Local LLM Tester (GPU Optimized) ---")
    print("Type 'exit' to quit.\n")
    
    from app.core.config import settings
    model_name = settings.OLLAMA_MODEL
    
    # Increase timeout for potential model loading
    async with httpx.AsyncClient(timeout=120.0) as client:
        while True:
            try:
                user_input = input("You: ")
                if user_input.lower() in ['exit', 'quit']:
                    break
                    
                # Using /api/generate with stream=True
                response = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": user_input,
                        "stream": True
                    }
                )
                
                if response.status_code != 200:
                    print(f"Error: Ollama returned {response.status_code}")
                    continue

                print("AI: ", end="", flush=True)
                async for line in response.aiter_lines():
                    if line:
                        chunk = json.loads(line)
                        print(chunk.get("response", ""), end="", flush=True)
                        if chunk.get("done"):
                            print("\n")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\nError: {str(e)}")

if __name__ == "__main__":
    try:
        asyncio.run(chat())
    except KeyboardInterrupt:
        pass
