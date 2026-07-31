from __future__ import annotations

import os


VPN_SUBSCRIPTION_BASE_URL = os.getenv(
    "VPN_SUBSCRIPTION_BASE_URL",
    "https://beatvault.ru",
)
VPN_AGENT_TOKEN = os.getenv("VPN_AGENT_TOKEN")
