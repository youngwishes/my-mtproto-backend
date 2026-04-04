import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_AUTH_TOKEN = os.getenv("BOT_AUTH_TOKEN")
BOT_LINK = os.getenv("BOT_LINK", "https://t.me/mtproto_keys_bot")
TELEGRAM_TIMEOUT = int(os.getenv("TELEGRAM_TIMEOUT", 5))
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "-1003695571259")
MY_TELEGRAM_ID = os.getenv("MY_TELEGRAM_ID")
