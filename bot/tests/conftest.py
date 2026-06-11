import importlib.util
import os
import sys
from pathlib import Path

# Ensure src/ appears before '' on sys.path so that `import bot` resolves to
# src/bot.py rather than the outer bot/ package directory.
_src = str(Path(__file__).parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

# Set env vars before any module import that reads them.
# Token must match aiogram's format: <digits>:<35-char alphanumeric+dash string>
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456789:AABBCCDDEEFFaabbccddeeff-1234567890")
os.environ.setdefault("API_URL", "http://test.api")
os.environ.setdefault("BOT_AUTH_TOKEN", "test-bot-auth")
os.environ.setdefault("MY_TELEGRAM_ID", "99999")
os.environ.setdefault("PROVIDER_TOKEN", "test-provider")

# Force `bot` to resolve to src/bot.py rather than the bot/ package directory.
# Without this, `from bot import bot` in core/handle_error.py would find
# the outer bot/__init__.py (empty package) instead of src/bot.py.
_bot_src = Path(_src) / "bot.py"
_spec = importlib.util.spec_from_file_location("bot", _bot_src)
_bot_module = importlib.util.module_from_spec(_spec)
sys.modules["bot"] = _bot_module
_spec.loader.exec_module(_bot_module)
