from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from apps.payments.clients import get_crypto_pay_client


class TestCryptoPaySettings(SimpleTestCase):
    @override_settings(CRYPTOPAY_API_TOKEN="", CRYPTOPAY_REQUEST_TIMEOUT=5.0)
    def test_factory_rejects_missing_token_without_disclosing_a_value(self) -> None:
        with self.assertRaisesRegex(
            ImproperlyConfigured,
            "^CRYPTOPAY_API_TOKEN is required$",
        ):
            get_crypto_pay_client()

    @override_settings(CRYPTOPAY_API_TOKEN="test-token", CRYPTOPAY_REQUEST_TIMEOUT=0)
    def test_factory_rejects_non_positive_timeout(self) -> None:
        with self.assertRaisesRegex(
            ImproperlyConfigured,
            "^CRYPTOPAY_REQUEST_TIMEOUT must be positive$",
        ):
            get_crypto_pay_client()

    @override_settings(
        CRYPTOPAY_API_TOKEN="test-token",
        CRYPTOPAY_BASE_URL="https://testnet-pay.crypt.bot",
        CRYPTOPAY_REQUEST_TIMEOUT=5.0,
    )
    def test_factory_reads_backend_only_settings(self) -> None:
        client = get_crypto_pay_client()

        self.assertEqual(client.base_url, "https://testnet-pay.crypt.bot")
        self.assertEqual(client.api_token, "test-token")
        self.assertEqual(client.timeout, 5.0)
