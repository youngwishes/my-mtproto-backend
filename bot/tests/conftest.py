import os

import pytest

from src.domains.links import MyServers, ServerItem

# Modules under src/ read configuration from the environment at import time
# (e.g. src.bot constructs a Bot with the token). Provide deterministic dummy
# values so importing them during tests never depends on a real .env.
os.environ.setdefault(
    "TELEGRAM_BOT_TOKEN", "123456:AAE-ExampleTokenForTestsOnly1234567890"
)
os.environ.setdefault("API_URL", "http://backend")
os.environ.setdefault("BOT_AUTH_TOKEN", "test-auth")
os.environ.setdefault("MY_TELEGRAM_ID", "1")
os.environ.setdefault(
    "FORTUNE_WHEEL_URL",
    "https://dash.mtprotokeys.com/fortune-wheel/",
)


@pytest.fixture
def servers() -> MyServers:
    return MyServers(
        expired_date="2026-07-14",
        servers=[ServerItem(location="🇳🇱 Нидерланды", proxy_link="tg://proxy?a=1")],
    )
