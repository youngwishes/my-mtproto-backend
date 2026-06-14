from __future__ import annotations

from django.conf import settings
from django.test import SimpleTestCase


class TestReconcileSettings(SimpleTestCase):
    def test_tls_domain_defined(self) -> None:
        self.assertTrue(hasattr(settings, "TLS_DOMAIN"))
        self.assertEqual(settings.TLS_DOMAIN, "beatvault.ru")

    def test_global_keys_limit_is_int(self) -> None:
        self.assertTrue(hasattr(settings, "GLOBAL_KEYS_LIMIT"))
        self.assertIsInstance(settings.GLOBAL_KEYS_LIMIT, int)
