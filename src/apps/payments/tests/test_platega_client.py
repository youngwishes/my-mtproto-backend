from __future__ import annotations

import json
from copy import deepcopy
from decimal import Decimal
from uuid import UUID

import requests
import responses
from django.test import SimpleTestCase, override_settings

from apps.payments.clients import PlategaClient
from apps.payments.exceptions import PlategaClientError


TRANSACTION_ID = "f8ea17f7-33bd-4a76-b2e6-f37d67eb512d"
PUBLIC_ID = UUID("0f57a4f1-1956-45be-8dc0-d891c00c74c1")
BOT_LINK = "https://t.me/mtproto_keys_bot"
ENDPOINT = "https://pay.platega.example/transaction/process"
VALID_TRANSACTION_JSON = {
    "transactionId": TRANSACTION_ID,
    "status": "PENDING",
    "redirect": "https://pay.platega.example/redirect",
    "expiresIn": "00:15:00",
}


@override_settings(BOT_LINK=BOT_LINK)
class TestPlategaClient(SimpleTestCase):
    def setUp(self) -> None:
        self.client = PlategaClient(
            base_url="https://pay.platega.example",
            merchant_id="merchant-id",
            secret="test-secret",
            timeout=5.0,
        )

    def _create_transaction(self):
        return self.client.create_transaction(
            amount=Decimal("99.00"),
            description='MTProto "30" days',
            return_url=BOT_LINK,
            public_id=PUBLIC_ID,
            telegram_id="123456789",
            telegram_username="@buyer",
        )

    @responses.activate
    def test_posts_exact_decimal_safe_sbp_payload_and_normalizes_response(self) -> None:
        responses.post(ENDPOINT, json=VALID_TRANSACTION_JSON, status=200)

        result = self._create_transaction()

        request = responses.calls[0].request
        body = request.body.decode() if isinstance(request.body, bytes) else request.body
        self.assertEqual(request.headers["X-MerchantId"], "merchant-id")
        self.assertEqual(request.headers["X-Secret"], "test-secret")
        self.assertEqual(request.headers["Content-Type"], "application/json")
        self.assertIn('"amount":99.00', body)
        self.assertEqual(
            json.loads(body),
            {
                "paymentMethod": 2,
                "paymentDetails": {"amount": 99.0, "currency": "RUB"},
                "description": 'MTProto "30" days',
                "return": BOT_LINK,
                "failedUrl": BOT_LINK,
                "payload": str(PUBLIC_ID),
                "metadata": {"userId": "123456789", "userName": "@buyer"},
            },
        )
        self.assertEqual(result.transaction_id, UUID(TRANSACTION_ID))
        self.assertEqual(result.status, "PENDING")
        self.assertEqual(result.redirect_url, "https://pay.platega.example/redirect")
        self.assertEqual(result.expires_in.total_seconds(), 900)

    @responses.activate
    def test_uses_telegram_id_as_missing_username_fallback(self) -> None:
        responses.post(ENDPOINT, json=VALID_TRANSACTION_JSON, status=200)

        self.client.create_transaction(
            amount=Decimal("99.00"),
            description="MTProto",
            return_url=BOT_LINK,
            public_id=PUBLIC_ID,
            telegram_id="123456789",
            telegram_username="",
        )

        request = responses.calls[0].request
        body = request.body.decode() if isinstance(request.body, bytes) else request.body
        self.assertEqual(json.loads(body)["metadata"], {"userId": "123456789", "userName": "123456789"})

    @responses.activate
    def test_accepts_matching_optional_echoes_in_object_or_json_string_form(self) -> None:
        for payment_details in (
            {"amount": "99.00", "currency": "RUB"},
            '{"amount": 99.00, "currency": "RUB"}',
        ):
            with self.subTest(payment_details=payment_details):
                payload = deepcopy(VALID_TRANSACTION_JSON)
                payload.update(
                    {
                        "paymentMethod": "SBPQR",
                        "paymentDetails": payment_details,
                        "return": BOT_LINK,
                        "merchantId": "merchant-id",
                    }
                )
                responses.reset()
                responses.post(ENDPOINT, json=payload, status=200)

                self.assertEqual(self._create_transaction().transaction_id, UUID(TRANSACTION_ID))

    @responses.activate
    def test_rejects_mismatch_or_unusable_creation_response_with_safe_code(self) -> None:
        cases = (
            ("status", "CONFIRMED", "create_mismatch"),
            ("transactionId", "not-a-uuid", "malformed"),
            ("redirect", "http://pay.platega.example/redirect", "malformed"),
            ("expiresIn", "00:14:59", "malformed"),
            ("paymentMethod", "CARD", "create_mismatch"),
            ("merchantId", "other-merchant", "create_mismatch"),
            ("return", "https://example.test", "create_mismatch"),
            ("paymentDetails", {"amount": "98.00", "currency": "RUB"}, "create_mismatch"),
            ("paymentDetails", {"amount": "99.00", "currency": "USD"}, "create_mismatch"),
        )
        for field, value, code in cases:
            with self.subTest(field=field, value=value):
                payload = deepcopy(VALID_TRANSACTION_JSON)
                payload[field] = value
                responses.reset()
                responses.post(ENDPOINT, json=payload, status=200)

                with self.assertRaisesRegex(PlategaClientError, f"^{code}$"):
                    self._create_transaction()

    @responses.activate
    def test_rejects_non_200_invalid_json_and_timeout_without_sensitive_values(self) -> None:
        cases = (
            ("unavailable", {"status": 201, "json": VALID_TRANSACTION_JSON}),
            ("malformed", {"status": 200, "body": "sensitive response body"}),
            ("timeout", {"status": 200, "body": requests.Timeout("sensitive request body")}),
        )
        for code, response_kwargs in cases:
            with self.subTest(code=code):
                responses.reset()
                responses.post(ENDPOINT, **response_kwargs)

                with self.assertRaisesRegex(PlategaClientError, f"^{code}$") as error:
                    self._create_transaction()

                self.assertNotIn("test-secret", str(error.exception))
                self.assertNotIn(str(PUBLIC_ID), str(error.exception))
                self.assertIsNone(error.exception.__cause__)
                self.assertIsNone(error.exception.__context__)

    @responses.activate
    def test_rejects_non_object_response_and_uses_configured_timeout(self) -> None:
        responses.post(ENDPOINT, json=[], status=200)

        with self.assertRaisesRegex(PlategaClientError, "^malformed$"):
            self._create_transaction()

        request = responses.calls[0].request
        self.assertEqual(request.body.__class__, bytes)

    @responses.activate
    def test_rejects_https_redirect_without_hostname_or_valid_port(self) -> None:
        for redirect in (
            "https://:443/redirect",
            "https://pay.platega.example:invalid/redirect",
        ):
            with self.subTest(redirect=redirect):
                payload = deepcopy(VALID_TRANSACTION_JSON)
                payload["redirect"] = redirect
                responses.reset()
                responses.post(ENDPOINT, json=payload, status=200)

                with self.assertRaisesRegex(PlategaClientError, "^malformed$"):
                    self._create_transaction()
