from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Brandwright AI Review Engine API"
    database_url: str = "sqlite:///./brandwright_review_engine.db"
    max_upload_bytes: int = 10 * 1024 * 1024
    cors_origins: str = "http://localhost:3000,http://localhost:3001"
    model_mode: str = "mock"
    model_name: str = "claude-sonnet-4-5"
    anthropic_api_key: str | None = None
    local_only_default: bool = True
    model_config = SettingsConfigDict(env_file=".env", env_prefix="BRANDWRIGHT_", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()
