import os


SUBSCRIPTION_PERIOD_DAYS = 30

CRYPTOPAY_API_TOKEN = os.environ.get("CRYPTOPAY_API_TOKEN", "")
CRYPTOPAY_BASE_URL = os.environ.get(
    "CRYPTOPAY_BASE_URL",
    "https://pay.crypt.bot",
)
CRYPTOPAY_WEBHOOK_SECRET = os.environ.get("CRYPTOPAY_WEBHOOK_SECRET", "")
CRYPTOPAY_REQUEST_TIMEOUT = float(os.environ.get("CRYPTOPAY_REQUEST_TIMEOUT", "5"))

PLATEGA_MERCHANT_ID = os.environ.get("PLATEGA_MERCHANT_ID", "")
PLATEGA_SECRET = os.environ.get("PLATEGA_SECRET", "")
PLATEGA_BASE_URL = os.environ.get("PLATEGA_BASE_URL", "https://pay.platega.io")
PLATEGA_REQUEST_TIMEOUT = float(os.environ.get("PLATEGA_REQUEST_TIMEOUT", "5"))
