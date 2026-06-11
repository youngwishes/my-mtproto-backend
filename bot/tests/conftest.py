import os

# Set env vars before any module import that reads them
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:test_token")
os.environ.setdefault("API_URL", "http://test.api")
os.environ.setdefault("BOT_AUTH_TOKEN", "test-bot-auth")
os.environ.setdefault("MY_TELEGRAM_ID", "99999")
os.environ.setdefault("PROVIDER_TOKEN", "test-provider")
