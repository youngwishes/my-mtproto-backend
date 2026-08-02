from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch

from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.payments.exceptions import (
    CryptoInvoiceCreationInProgress,
    CryptoInvoiceUnavailable,
)
from apps.payments.services.dtos import CreateCryptoInvoiceOut

_SERVICE_FACTORY = "apps.payments.api.v1.views.crypto_pay_views.get_create_or_reuse_crypto_invoice_service"


class TestCreateCryptoInvoiceView(APITestCase):
    url: str = reverse("crypto-invoice-create")

    def _post(self, data: dict[str, str]):
        return self.client.post(self.url, data, headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN})

    def test_create_invoice_requires_bot_auth_token(self) -> None:
        response = self.client.post(
            self.url,
            {"username": "1487189460", "purchase_kind": "subscription"},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch(_SERVICE_FACTORY)
    def test_create_invoice_rejects_unknown_kind(self, get_service: Mock) -> None:
        response = self._post({"username": "1487189460", "purchase_kind": "arbitrary_product"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        get_service.assert_not_called()

    @patch(_SERVICE_FACTORY)
    def test_new_invoice_returns_exact_four_fields(self, get_service: Mock) -> None:
        get_service.return_value.return_value = CreateCryptoInvoiceOut(
            invoice_url="https://t.me/CryptoBot?start=invoice",
            rub_amount=Decimal("99.00"),
            expires_at=datetime(2026, 8, 2, 12, 30, tzinfo=UTC),
            reused=False,
        )
        response = self._post({"username": "1487189460", "purchase_kind": "subscription"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "invoice_url": "https://t.me/CryptoBot?start=invoice",
                "rub_amount": "99.00",
                "expires_at": "2026-08-02T12:30:00Z",
                "reused": False,
            },
        )

    @patch(_SERVICE_FACTORY)
    def test_reused_invoice_returns_same_values_and_reused_true(
        self, get_service: Mock
    ) -> None:
        get_service.return_value.return_value = CreateCryptoInvoiceOut(
            invoice_url="https://t.me/CryptoBot?start=reused",
            rub_amount=Decimal("149.00"),
            expires_at=datetime(2026, 8, 2, 12, 30, tzinfo=UTC),
            reused=True,
        )
        response = self._post({"username": "1487189460", "purchase_kind": "vpn_subscription"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "invoice_url": "https://t.me/CryptoBot?start=reused",
                "rub_amount": "149.00",
                "expires_at": "2026-08-02T12:30:00Z",
                "reused": True,
            },
        )

    @patch(_SERVICE_FACTORY)
    def test_creation_in_progress_returns_safe_409(self, get_service: Mock) -> None:
        get_service.return_value.side_effect = CryptoInvoiceCreationInProgress(
            "1487189460", reason_code="creating"
        )
        response = self._post({"username": "1487189460", "purchase_kind": "gift_certificate"})
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.json()["detail"], {"reason_code": "creating"})

    @override_settings(CRYPTOPAY_API_TOKEN="super-secret-api-token")
    @patch(_SERVICE_FACTORY)
    def test_provider_error_returns_safe_503_without_secret(
        self, get_service: Mock
    ) -> None:
        for reason_code in ("cryptopay_timeout", "database_locked"):
            with self.subTest(reason_code=reason_code):
                get_service.return_value.side_effect = CryptoInvoiceUnavailable(
                    "1487189460", reason_code=reason_code
                )
                response = self._post({"username": "1487189460", "purchase_kind": "subscription"})
                self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
                self.assertEqual(response.json()["detail"], {"reason_code": reason_code})
                self.assertNotIn("super-secret-api-token", response.content.decode())
