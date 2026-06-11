from __future__ import annotations

import os


def _require(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        raise RuntimeError(f"Required environment variable {name!r} is not set")
    return value


BOT_TOKEN: str = _require("TELEGRAM_BOT_TOKEN")
API_URL: str = _require("API_URL")
MY_TELEGRAM_ID: str = _require("MY_TELEGRAM_ID")
BOT_AUTH_TOKEN: str = _require("BOT_AUTH_TOKEN")
PROVIDER_TOKEN: str = _require("PROVIDER_TOKEN")
