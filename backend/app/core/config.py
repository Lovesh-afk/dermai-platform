"""
Centralized settings, loaded from environment variables.
Never hardcode secrets or connection strings elsewhere in the app —
everything goes through this module so config has one source of truth.
"""
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"

    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "amqp://guest:guest@localhost:5672//"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # The inference microservice (ai/service). "inference" is its
    # docker-compose service name, so this default works inside compose.
    INFERENCE_SERVICE_URL: str = "http://inference:8001"

    # Chatbot (Phase 9). Leave GEMINI_API_KEY empty to run the chatbot in
    # knowledge-base-only mode; set it in .env to enable AI answers.
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    LLM_TIMEOUT_SECONDS: float = 30.0

    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_BUCKET: str = ""
    AWS_REGION: str = "us-east-1"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        return v


settings = Settings()
