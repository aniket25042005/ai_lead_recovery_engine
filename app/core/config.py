import os
from typing import Literal, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Zizzet AI Lead Recovery Engine"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/zizzet_recovery"
    SQLITE_FALLBACK_URL: str = "sqlite:///./zizzet_recovery.db"
    FALLBACK_TO_SQLITE_ON_DB_ERROR: bool = True
    DB_POOL_PRE_PING: bool = True
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # LLM Settings
    LLM_PROVIDER: Literal["gemini", "openai", "mock"] = "mock"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    LLM_MAX_RETRIES: int = 3
    LLM_TIMEOUT_SECONDS: int = 25
    PROMPT_VERSION: str = "v1.0"

    # Background Queue / Concurrency
    QUEUE_WORKERS: int = 2
    REDIS_URL: Optional[str] = None

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
