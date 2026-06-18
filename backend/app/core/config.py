from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env from the backend/ dir first, then the project root
_ENV_FILE = ".env" if Path(".env").exists() else str(Path(__file__).resolve().parents[3] / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    # Azure OpenAI
    azure_openai_api_key: str
    azure_openai_endpoint: str
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"

    # PostgreSQL
    postgres_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ecomm_ops"

    @property
    def postgres_url_plain(self) -> str:
        """psycopg3-compatible URL (no driver prefix) for LangGraph checkpointer."""
        return self.postgres_url.replace("postgresql+asyncpg://", "postgresql://")

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "incidents"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Langfuse
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # App
    # repo_backend versions:
    #   v1 (or "mock")     — hardcoded mock data, no DB required
    #   v2 (or "postgres") — live PostgreSQL data
    repo_backend: str = "v2"  # "v1" | "v2"
    api_secret_key: str = "change-me"
    frontend_url: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
