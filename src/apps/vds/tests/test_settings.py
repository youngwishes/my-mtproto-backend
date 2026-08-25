from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class TestReconcileSettings(SimpleTestCase):
    def test_tls_domain_is_not_defined(self) -> None:
        self.assertFalse(hasattr(settings, "TLS_DOMAIN"))

    def test_env_example_omits_tls_domain(self) -> None:
        env_example = (Path(__file__).resolve().parents[4] / ".env.example").read_text(
            encoding="utf-8"
        )

        self.assertFalse(
            any(line.startswith("TLS_DOMAIN=") for line in env_example.splitlines())
        )

    def test_global_keys_limit_is_int(self) -> None:
        self.assertTrue(hasattr(settings, "GLOBAL_KEYS_LIMIT"))
        self.assertIsInstance(settings.GLOBAL_KEYS_LIMIT, int)
