from __future__ import annotations

from functools import lru_cache
from typing import final

from pydantic_settings import BaseSettings, SettingsConfigDict


@final
class Settings(BaseSettings):
    """Validated application configuration.

    Values come from the environment (case-insensitive) and, for local runs,
    a ``.env`` file. Constructing this fails loudly if a required variable is
    missing or malformed — so misconfiguration surfaces at startup, not mid-update.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    telegram_bot_token: str
    api_url: str
    my_telegram_id: int
    bot_auth_token: str
    provider_token: str


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
