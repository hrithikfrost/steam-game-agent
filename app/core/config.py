from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Steam Game AI Agent"
    environment: str = "local"
    database_url: str
    database_ssl: bool = False
    supabase_project_ref: str | None = None
    telegram_bot_token: str = Field(default="")
    openai_api_key: str = Field(default="")
    openai_model: str = "gpt-4.1-mini"
    steam_api_key: str = Field(default="")
    rawg_api_key: str = Field(default="")
    daily_recommendation_hour: int = 10
    daily_recommendation_timezone: str = "Europe/Minsk"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
