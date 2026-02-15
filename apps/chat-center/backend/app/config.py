"""Application settings and configuration"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Database
    DATABASE_URL: str = "postgresql://postgres:agentiq123@localhost:5432/agentiq_chat"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "change-me-in-production"
    ENCRYPTION_KEY: str  # Required, generated with Fernet.generate_key()

    # Ozon API (demo)
    OZON_CLIENT_ID: Optional[str] = None
    OZON_API_KEY: Optional[str] = None

    # DeepSeek AI
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"

    # LLM-based question intent classification (fallback when rule-based returns general_question)
    ENABLE_LLM_INTENT: bool = False

    # WB API Rate Limiting
    WB_RATE_LIMIT_RPM: int = 30  # Max requests per minute per seller (WB typical limit)

    # App config
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Celery
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None

    # Sentry Error Tracking (optional)
    SENTRY_DSN: str = ""  # Empty string = disabled
    SENTRY_ENVIRONMENT: str = "production"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
