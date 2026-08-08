from __future__ import annotations

from math import inf, nan

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from apps.payments.clients import get_platega_client


class TestPlategaSettings(SimpleTestCase):
    @override_settings(
        PLATEGA_MERCHANT_ID=" ",
        PLATEGA_SECRET="test-secret",
        PLATEGA_BASE_URL="https://pay.platega.example",
        PLATEGA_REQUEST_TIMEOUT=5.0,
    )
    def test_factory_rejects_blank_credentials_without_disclosing_them(self) -> None:
        with self.assertRaisesRegex(
            ImproperlyConfigured,
            "^PLATEGA_MERCHANT_ID is required$",
        ) as error:
            get_platega_client()

        self.assertNotIn("test-secret", str(error.exception))

    @override_settings(
        PLATEGA_MERCHANT_ID="merchant",
        PLATEGA_SECRET="secret",
        PLATEGA_BASE_URL="http://pay.platega.example",
        PLATEGA_REQUEST_TIMEOUT=5.0,
    )
    def test_factory_rejects_non_https_base_url(self) -> None:
        with self.assertRaisesRegex(
            ImproperlyConfigured,
            "^PLATEGA_BASE_URL must be an HTTPS URL$",
        ):
            get_platega_client()

    def test_factory_requires_base_url_hostname_and_valid_port(self) -> None:
        for base_url in ("https://:443", "https://pay.platega.example:invalid"):
            with self.subTest(base_url=base_url), override_settings(
                PLATEGA_MERCHANT_ID="merchant",
                PLATEGA_SECRET="secret",
                PLATEGA_BASE_URL=base_url,
                PLATEGA_REQUEST_TIMEOUT=5.0,
            ):
                with self.assertRaisesRegex(
                    ImproperlyConfigured,
                    "^PLATEGA_BASE_URL must be an HTTPS URL$",
                ):
                    get_platega_client()

    @override_settings(
        PLATEGA_MERCHANT_ID="merchant",
        PLATEGA_SECRET="secret",
        PLATEGA_BASE_URL="https://pay.platega.example",
        PLATEGA_REQUEST_TIMEOUT=0,
    )
    def test_factory_rejects_non_positive_timeout(self) -> None:
        with self.assertRaisesRegex(
            ImproperlyConfigured,
            "^PLATEGA_REQUEST_TIMEOUT must be positive$",
        ):
            get_platega_client()

    def test_factory_rejects_non_finite_timeout(self) -> None:
        for timeout in (nan, inf, -inf):
            with self.subTest(timeout=timeout), override_settings(
                PLATEGA_MERCHANT_ID="merchant",
                PLATEGA_SECRET="secret",
                PLATEGA_BASE_URL="https://pay.platega.example",
                PLATEGA_REQUEST_TIMEOUT=timeout,
            ):
                with self.assertRaisesRegex(
                    ImproperlyConfigured,
                    "^PLATEGA_REQUEST_TIMEOUT must be positive$",
                ):
                    get_platega_client()

    @override_settings(
        PLATEGA_MERCHANT_ID="merchant",
        PLATEGA_SECRET="secret",
        PLATEGA_BASE_URL="https://pay.platega.example/",
        PLATEGA_REQUEST_TIMEOUT=7.5,
    )
    def test_factory_reads_only_backend_settings(self) -> None:
        client = get_platega_client()

        self.assertEqual(client.base_url, "https://pay.platega.example/")
        self.assertEqual(client.merchant_id, "merchant")
        self.assertEqual(client.secret, "secret")
        self.assertEqual(client.timeout, 7.5)
