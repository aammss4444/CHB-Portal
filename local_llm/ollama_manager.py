import subprocess
import os

def check_ollama_running():
    try:
        import httpx
        import asyncio
        async def check():
            async with httpx.AsyncClient() as client:
                try:
                    res = await client.get("http://localhost:11434/api/tags")
                    return res.status_code == 200
                except:
                    return False
        return asyncio.run(check())
    except:
        return False

def ensure_llama31():
    print("Checking for Llama 3.2 (GPU Optimized)...")
    result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    if "llama3.2" not in result.stdout:
        print("Llama 3.2 not found. Downloading...")
        subprocess.run(["ollama", "pull", "llama3.2"])
    else:
        print("Llama 3.2 is ready and optimized for your 4GB GPU.")

if __name__ == "__main__":
    if not check_ollama_running():
        print("Error: Ollama is not running. Please start Ollama desktop application.")
    else:
        print("Ollama is running.")
        ensure_llama31()
