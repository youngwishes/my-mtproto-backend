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
    PlategaInvoiceCreationInProgress,
    PlategaInvoiceUnavailable,
)
from apps.payments.services.dtos import CreatePlategaInvoiceOut


_SERVICE_FACTORY = "apps.payments.api.v1.views.platega_views.get_create_or_reuse_platega_invoice_service"


class TestCreatePlategaInvoiceView(APITestCase):
    url: str = reverse("platega-invoice-create")

    def _post(self, data: dict[str, str]):
        return self.client.post(
            self.url,
            data,
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

    def test_requires_bot_auth_token(self) -> None:
        response = self.client.post(
            self.url,
            {"username": "1487189460", "purchase_kind": "subscription"},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch(_SERVICE_FACTORY)
    def test_all_supported_kinds_return_exact_safe_response(self, get_service: Mock) -> None:
        cases = (
            ("subscription", "99.00", False),
            ("vpn_subscription", "149.00", True),
            ("gift_certificate", "99.00", False),
        )
        for purchase_kind, rub_amount, reused in cases:
            with self.subTest(purchase_kind=purchase_kind):
                get_service.return_value.return_value = CreatePlategaInvoiceOut(
                    payment_url="https://pay.example/transaction",
                    rub_amount=Decimal(rub_amount),
                    expires_at=datetime(2026, 8, 2, 12, 15, tzinfo=UTC),
                    reused=reused,
                )
                response = self._post(
                    {"username": "1487189460", "purchase_kind": purchase_kind}
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(
                    response.json(),
                    {
                        "payment_url": "https://pay.example/transaction",
                        "rub_amount": rub_amount,
                        "expires_at": "2026-08-02T12:15:00Z",
                        "reused": reused,
                    },
                )

    @patch(_SERVICE_FACTORY)
    def test_invalid_input_returns_400_without_calling_service(self, get_service: Mock) -> None:
        response = self._post(
            {"username": "1487189460", "purchase_kind": "unsupported"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        get_service.assert_not_called()

    @patch(_SERVICE_FACTORY)
    def test_creation_conflict_returns_safe_409(self, get_service: Mock) -> None:
        get_service.return_value.side_effect = PlategaInvoiceCreationInProgress(
            "1487189460",
            reason_code="creating",
        )
        response = self._post(
            {"username": "1487189460", "purchase_kind": "subscription"}
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.json()["detail"], {"reason_code": "creating"})

    @override_settings(PLATEGA_SECRET="provider-secret")
    @patch(_SERVICE_FACTORY)
    def test_provider_or_storage_error_returns_safe_503(self, get_service: Mock) -> None:
        for reason_code in (
            "timeout",
            "database_error",
            "database_locked",
            "payment_method_unavailable",
        ):
            with self.subTest(reason_code=reason_code):
                get_service.return_value.side_effect = PlategaInvoiceUnavailable(
                    "1487189460",
                    reason_code=reason_code,
                )
                response = self._post(
                    {"username": "1487189460", "purchase_kind": "subscription"}
                )
                self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
                self.assertEqual(response.json()["detail"], {"reason_code": reason_code})
                self.assertNotIn("provider-secret", response.content.decode())
