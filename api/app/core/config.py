from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "ColdReach"
    environment: str = Field(default="development")
    debug: bool = Field(default=True)
    secret_key: str = Field(default="dev-insecure-secret-key-change-me")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://coldreach:coldreach@localhost:5432/coldreach"
    )

    # Redis / Celery
    redis_url: str = Field(default="redis://localhost:6379/0")
    celery_broker_url: str = Field(default="redis://localhost:6379/1")
    celery_result_backend: str = Field(default="redis://localhost:6379/2")

    # Auth
    admin_email: str = Field(default="admin@example.com")
    admin_password: str = Field(default="change-me")
    session_cookie_name: str = "coldreach_session"
    session_max_age_seconds: int = 60 * 60 * 24 * 14

    # Encryption for credentials at rest (Fernet key, 32 url-safe base64 bytes)
    credentials_encryption_key: str = Field(default="")

    # LLM
    llm_provider: str = Field(default="groq")
    groq_api_key: str = Field(default="")

    # Enrichment
    hunter_api_key: str = Field(default="")
    apollo_api_key: str = Field(default="")

    # Sending caps
    default_daily_send_cap: int = 40
    absolute_daily_send_cap_ceiling: int = 150

    # Google OAuth (identifies the ColdReach app to Google; per-account tokens are
    # stored encrypted on the SendingAccount row, not here)
    google_oauth_client_id: str = Field(default="")
    google_oauth_client_secret: str = Field(default="")
    google_oauth_redirect_uri: str = Field(
        default="http://localhost:8000/sending-accounts/oauth/gmail/callback"
    )

    # CORS
    web_origin: str = Field(default="http://localhost:3000")

    # Storage
    resume_storage_dir: str = Field(default="./storage/resumes")


@lru_cache
def get_settings() -> Settings:
    return Settings()
