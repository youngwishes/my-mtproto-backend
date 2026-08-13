from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class TestVPNSettings(SimpleTestCase):
    def test_subscription_base_url_default(self) -> None:
        self.assertEqual(settings.VPN_SUBSCRIPTION_BASE_URL, "https://dash.mtprotokeys.com")

    def test_env_example_uses_subscription_base_url_default(self) -> None:
        env_example = (Path(__file__).resolve().parents[4] / ".env.example").read_text(
            encoding="utf-8"
        )

        self.assertIn("VPN_SUBSCRIPTION_BASE_URL=https://dash.mtprotokeys.com", env_example)
