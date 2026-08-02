from __future__ import annotations

import copy
import hashlib
import hmac
import json
from datetime import UTC, datetime
from unittest import mock

from django.db import OperationalError
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.payments.enums import CryptoPaymentIntentStatusEnum
from apps.payments.exceptions import CryptoPaymentRetryable
from apps.payments.models import Payment
from apps.payments.services.dtos import ApplyCryptoPaymentOut
from apps.payments.tests.factories import CryptoPaymentIntentFactory

_VIEW = "apps.payments.api.v1.views.crypto_pay_views"
_URL = "/api/v1/payments/crypto/webhooks/path-secret/"
_RAW_EVENT = b'{"update_id":42,"update_type":"invoice_paid","payload":{"invoice_id":731,"status":"paid"}}'
_KNOWN_SIGNATURE = "9c24a84ebef30ce6a15dbc899b3aed0cb267dd4697623a0b96e5624072849d29"


def _signature(*, raw: bytes, token: str = "test-api-token") -> str:
    key = hashlib.sha256(token.encode()).digest()
    return hmac.new(key, raw, hashlib.sha256).hexdigest()


@override_settings(
    CRYPTOPAY_API_TOKEN="test-api-token",
    CRYPTOPAY_WEBHOOK_SECRET="path-secret",
)
class TestCryptoPayWebhookView(APITestCase):
    expires_at = datetime(2026, 8, 2, 12, 30, tzinfo=UTC)

    def setUp(self) -> None:
        self.intent = CryptoPaymentIntentFactory(
            public_id="0f57a4f1-1956-45be-8dc0-d891c00c74c1",
            status=CryptoPaymentIntentStatusEnum.ACTIVE,
            provider_invoice_id=731,
            provider_expires_at=self.expires_at,
        )
        self.apply = mock.Mock()
        self.get_apply = mock.patch(
            f"{_VIEW}.get_apply_crypto_payment_service",
            return_value=self.apply,
        ).start()
        self.warn = mock.patch(
            f"{_VIEW}.warn_crypto_webhook_admin_task",
        ).start()
        self.logger = mock.patch(f"{_VIEW}.logger").start()
        self.addCleanup(mock.patch.stopall)

    @staticmethod
    def event() -> dict[str, object]:
        return {
            "update_id": 42,
            "update_type": "invoice_paid",
            "payload": {
                "invoice_id": 731,
                "status": "paid",
                "currency_type": "fiat",
                "fiat": "RUB",
                "amount": "99.00",
                "accepted_assets": "USDT,TON",
                "paid_asset": "USDT",
                "payload": "0f57a4f1-1956-45be-8dc0-d891c00c74c1",
                "bot_invoice_url": "https://t.me/CryptoBot?start=private",
                "created_at": "2026-08-02T12:00:00Z",
                "expiration_date": "2026-08-02T12:30:00Z",
                "paid_at": "2026-08-02T12:20:00Z",
            },
        }

    def post_raw(
        self,
        raw: bytes,
        *,
        signature: str | None = None,
        secret: str = "path-secret",
    ):
        headers = {}
        if signature is not None:
            headers["HTTP_CRYPTO_PAY_API_SIGNATURE"] = signature
        return self.client.generic(
            "POST",
            f"/api/v1/payments/crypto/webhooks/{secret}/",
            raw,
            content_type="application/json",
            **headers,
        )

    def post_event(self, event: dict[str, object]):
        raw = json.dumps(event, separators=(",", ":")).encode()
        return self.post_raw(raw, signature=_signature(raw=raw))

    def assert_no_processing(self) -> None:
        self.get_apply.assert_not_called()
        self.warn.delay.assert_not_called()
        self.logger.warning.assert_not_called()

    def test_secret_and_hmac_fail_closed_before_parsing(self) -> None:
        cases = (
            ("wrong secret", {}, "wrong-secret", status.HTTP_404_NOT_FOUND),
            ("missing signature", {}, "path-secret", status.HTTP_401_UNAUTHORIZED),
            (
                "bad signature",
                {"signature": "bad-signature"},
                "path-secret",
                status.HTTP_401_UNAUTHORIZED,
            ),
        )
        for label, kwargs, secret, expected in cases:
            with self.subTest(label=label):
                response = self.post_raw(_RAW_EVENT, secret=secret, **kwargs)
                self.assertEqual(response.status_code, expected)
                self.assert_no_processing()

        with override_settings(CRYPTOPAY_WEBHOOK_SECRET=""):
            response = self.post_raw(_RAW_EVENT, signature=_KNOWN_SIGNATURE)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assert_no_processing()

        with override_settings(CRYPTOPAY_API_TOKEN=""):
            response = self.post_raw(_RAW_EVENT, signature=_KNOWN_SIGNATURE)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assert_no_processing()

    def test_hmac_uses_exact_raw_bytes_before_json_validation(self) -> None:
        response = self.post_raw(_RAW_EVENT, signature=_KNOWN_SIGNATURE)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_no_processing()

        spaced = b'{"update_id": 42, "update_type": "invoice_paid", "payload": {"invoice_id": 731, "status": "paid"}}'
        response = self.post_raw(spaced, signature=_KNOWN_SIGNATURE)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assert_no_processing()

    def test_malformed_and_unsupported_signed_events_are_400_without_warning(
        self,
    ) -> None:
        malformed = b'{"update_id":42'
        response = self.post_raw(malformed, signature=_signature(raw=malformed))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_no_processing()

        event = self.event()
        event["update_type"] = "invoice_created"
        response = self.post_event(event)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_no_processing()

    def test_each_signed_warning_logs_and_enqueues_only_safe_fields(self) -> None:
        cases = (
            ("invoice_id", 999999, "unknown_invoice", None),
            ("status", "active", "status_mismatch", self.intent.pk),
            ("payload", "wrong-public-id", "payload_mismatch", self.intent.pk),
            ("currency_type", "crypto", "fiat_mismatch", self.intent.pk),
            ("fiat", "USD", "fiat_mismatch", self.intent.pk),
            ("amount", "98.99", "amount_mismatch", self.intent.pk),
            (
                "accepted_assets",
                "USDT",
                "accepted_assets_mismatch",
                self.intent.pk,
            ),
            ("paid_asset", "BTC", "paid_asset_mismatch", self.intent.pk),
            (
                "expiration_date",
                "2026-08-02T12:31:00Z",
                "expiration_mismatch",
                self.intent.pk,
            ),
            ("paid_at", None, "paid_at_mismatch", self.intent.pk),
            (
                "paid_at",
                "2026-08-02T12:31:00Z",
                "paid_at_mismatch",
                self.intent.pk,
            ),
        )
        for field, value, reason, intent_id in cases:
            with self.subTest(field=field, value=value):
                event = copy.deepcopy(self.event())
                event["payload"][field] = value
                response = self.post_event(event)
                expected = {
                    "reason": reason,
                    "update_id": 42,
                    "invoice_id": event["payload"]["invoice_id"],
                    "intent_id": intent_id,
                }
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.get_apply.assert_not_called()
                self.logger.warning.assert_called_once_with(expected)
                self.warn.delay.assert_called_once_with(expected)
                self.logger.reset_mock()
                self.warn.reset_mock()

    def test_warning_enqueue_failure_is_retryable_without_fulfillment(self) -> None:
        event = self.event()
        event["payload"]["amount"] = "98.99"
        self.warn.delay.side_effect = RuntimeError("queue unavailable")

        response = self.post_event(event)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.apply.assert_not_called()
        self.warn.delay.assert_called_once()
        self.logger.warning.assert_called_once()

    def test_valid_and_duplicate_apply_results_are_200(self) -> None:
        for result in (
            ApplyCryptoPaymentOut(fulfilled=True, already_fulfilled=False),
            ApplyCryptoPaymentOut(fulfilled=False, already_fulfilled=True),
        ):
            with self.subTest(result=result):
                self.apply.return_value = result
                response = self.post_event(self.event())
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                payment = self.apply.call_args.kwargs["payment"]
                self.assertEqual(payment.intent_id, self.intent.pk)
                self.assertEqual(payment.invoice.invoice_id, 731)
                self.assertEqual(payment.invoice.accepted_assets, frozenset({"USDT", "TON"}))
                self.warn.delay.assert_not_called()
                self.apply.reset_mock()

    def test_temporary_apply_errors_return_503_and_leave_intent_unfinished(self) -> None:
        errors = (
            CryptoPaymentRetryable("1487189460", reason_code="processing"),
            OperationalError("database is locked"),
        )
        for error in errors:
            with self.subTest(error=type(error).__name__):
                self.apply.side_effect = error
                response = self.post_event(self.event())
                self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
                self.intent.refresh_from_db()
                self.assertEqual(self.intent.status, CryptoPaymentIntentStatusEnum.ACTIVE)
                self.assertEqual(Payment.objects.count(), 0)
                self.warn.delay.assert_not_called()
                self.apply.reset_mock(side_effect=True)

    def test_temporary_validator_database_error_returns_503(self) -> None:
        with mock.patch(
            f"{_VIEW}.get_validate_crypto_invoice_service"
        ) as get_validator:
            get_validator.return_value.side_effect = OperationalError(
                "database is locked"
            )
            self.client.raise_request_exception = False

            response = self.post_event(self.event())

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.apply.assert_not_called()
        self.warn.delay.assert_not_called()
