from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.config import Settings

ENV = {
    "TELEGRAM_BOT_TOKEN": "123456:token",
    "API_URL": "http://example",
    "MY_TELEGRAM_ID": "777",
    "BOT_AUTH_TOKEN": "auth",
    "PROVIDER_TOKEN": "prov",
}


@pytest.fixture
def env(monkeypatch):
    # Start from a clean slate so the developer's real .env never leaks in.
    for key in ENV:
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


def test_settings_loads_and_coerces_from_environment(env):
    for key, value in ENV.items():
        env.setenv(key, value)

    settings = Settings(_env_file=None)

    assert settings.telegram_bot_token == "123456:token"
    assert settings.api_url == "http://example"
    assert settings.my_telegram_id == 777  # coerced to int
    assert settings.bot_auth_token == "auth"
    assert settings.provider_token == "prov"


def test_settings_raises_when_required_var_missing(env):
    for key, value in ENV.items():
        if key != "API_URL":
            env.setenv(key, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_rejects_non_numeric_telegram_id(env):
    for key, value in ENV.items():
        env.setenv(key, value)
    env.setenv("MY_TELEGRAM_ID", "not-a-number")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
