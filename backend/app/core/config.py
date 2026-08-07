from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PocketPilot API"
    environment: str = "development"
    api_prefix: str = "/api"
    database_url: str = "sqlite:///./financial_planner.db"
    jwt_secret: str = Field(default="development-only-change-me", min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    cors_origins: str = "http://localhost:8081,http://localhost:19006"

    google_ios_client_id: str = ""
    google_android_client_id: str = ""
    google_web_client_id: str = ""
    allow_dev_login: bool = True

    ai_provider: str = "mock"
    ai_model: str = "mock-finance-agent-v2"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = ""
    ai_timeout_seconds: int = 25

    email_provider: str = "mock"
    email_from: str = "no-reply@example.com"
    sendgrid_api_key: str = ""
    resend_api_key: str = ""
    push_provider: str = "mock"
    expo_access_token: str = ""
    scheduler_enabled: bool = True
    scheduler_interval_seconds: int = 60

    app_group_id: str = "group.com.example.pocketpilot"
    proposal_expiry_minutes: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def google_client_ids(self) -> list[str]:
        return [value for value in [self.google_ios_client_id, self.google_android_client_id, self.google_web_client_id] if value]


@lru_cache
def get_settings() -> Settings:
    return Settings()
