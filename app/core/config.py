import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ENV: str = "dev"
    DEBUG: bool = False
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    MAX_DAILY_LECTURES: int = 6
    MAX_DAILY_LECTURES_POLICY: int = 6
    MIN_JOINING_DAYS: int = 0  # Set to 7 for production

    GEMINI_API_KEY: str = ""
    ENABLE_LLM: bool = False
    LLM_PROVIDER: str = "openai"  # "gemini", "ollama", or "openai"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini" # Using a cheap model as requested (placeholder for GPT-5.4 Nano)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:latest"
    LLM_TIMEOUT_SECONDS: int = 60
    ALLOW_MOCK_HISTORY: bool = False
    ALLOW_OCR_SIMULATION: bool = False
    CORS_ORIGINS: str = "http://localhost:5173"

    model_config = {
        "env_file": os.path.join(Path(__file__).parent.parent.parent, ".env"),
        "extra": "ignore"
    }

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        if self.DATABASE_URL.startswith("postgresql://"):
            return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.DATABASE_URL

settings = Settings()
