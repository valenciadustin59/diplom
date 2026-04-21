from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Site Audit API", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    database_url: str = Field(default="sqlite:///./audit.db", alias="DATABASE_URL")
    celery_broker_url: str = Field(default="redis://localhost:6379/0", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(
        default="redis://localhost:6379/0",
        alias="CELERY_RESULT_BACKEND",
    )
    serp_provider: str = Field(default="searxng", alias="SERP_PROVIDER")
    searxng_base_url: str | None = Field(default=None, alias="SEARXNG_BASE_URL")
    searxng_language: str = Field(default="ru-RU", alias="SEARXNG_LANGUAGE")
    search_timeout: float = Field(default=20.0, alias="SEARCH_TIMEOUT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
