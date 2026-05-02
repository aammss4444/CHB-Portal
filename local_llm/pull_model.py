import httpx
import asyncio

async def pull():
    print("Pulling Llama 3.2 (3B) for GPU acceleration...")
    async with httpx.AsyncClient(timeout=None) as client:
        try:
            async with client.stream("POST", "http://localhost:11434/api/pull", json={"name": "llama3.2"}) as response:
                async for line in response.aiter_lines():
                    if line:
                        import json
                        status = json.loads(line)
                        if "status" in status:
                            print(f"\rStatus: {status['status']} {status.get('completed', '')}/{status.get('total', '')}", end="", flush=True)
            print("\nPull complete.")
        except Exception as e:
            print(f"\nError: {str(e)}")

if __name__ == "__main__":
    asyncio.run(pull())
