from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class TestReconcileSettings(SimpleTestCase):
    def test_tls_domain_defined(self) -> None:
        self.assertTrue(hasattr(settings, "TLS_DOMAIN"))
        self.assertEqual(settings.TLS_DOMAIN, "mtprotokeys.com")

    def test_env_example_uses_tls_domain_default(self) -> None:
        env_example = (Path(__file__).resolve().parents[4] / ".env.example").read_text(
            encoding="utf-8"
        )

        self.assertIn("TLS_DOMAIN=mtprotokeys.com", env_example)

    def test_global_keys_limit_is_int(self) -> None:
        self.assertTrue(hasattr(settings, "GLOBAL_KEYS_LIMIT"))
        self.assertIsInstance(settings.GLOBAL_KEYS_LIMIT, int)
