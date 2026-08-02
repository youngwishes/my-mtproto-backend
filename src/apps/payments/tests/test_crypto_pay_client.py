from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import requests
import responses
from django.test import SimpleTestCase
from django.utils import timezone

from apps.payments.clients import CryptoPayClient
from apps.payments.exceptions import CryptoPayClientError


VALID_INVOICE_JSON = {
    "invoice_id": 731,
    "status": "paid",
    "currency_type": "fiat",
    "fiat": "RUB",
    "amount": "99.00",
    "accepted_assets": "USDT,TON",
    "paid_asset": "USDT",
    "payload": "0f57a4f1-1956-45be-8dc0-d891c00c74c1",
    "bot_invoice_url": "https://t.me/CryptoBot?start=test",
    "created_at": "2026-08-02T12:00:00Z",
    "expiration_date": "2026-08-02T12:30:00Z",
    "paid_at": "2026-08-02T12:20:00Z",
}


class TestCryptoPayClient(SimpleTestCase):
    def setUp(self) -> None:
        self.client = CryptoPayClient(
            base_url="https://testnet-pay.crypt.bot",
            api_token="test-token",
            timeout=5.0,
        )

    @responses.activate
    def test_create_invoice_sends_exact_fiat_payload_without_pii(self) -> None:
        responses.post(
            "https://testnet-pay.crypt.bot/api/createInvoice",
            json={"ok": True, "result": VALID_INVOICE_JSON},
        )

        result = self.client.create_invoice(
            amount=Decimal("99.00"),
            payload="0f57a4f1-1956-45be-8dc0-d891c00c74c1",
            description="MTProto на 30 дней",
        )

        request = responses.calls[0].request
        self.assertEqual(request.headers["Crypto-Pay-API-Token"], "test-token")
        self.assertEqual(
            parse_qs(request.body),
            {
                "currency_type": ["fiat"],
                "fiat": ["RUB"],
                "amount": ["99.00"],
                "accepted_assets": ["USDT,TON"],
                "expires_in": ["1800"],
                "payload": ["0f57a4f1-1956-45be-8dc0-d891c00c74c1"],
                "description": ["MTProto на 30 дней"],
            },
        )
        self.assertNotIn("telegram", request.body.lower())
        self.assertNotIn("username", request.body.lower())
        self.assertNotIn("email", request.body.lower())
        self.assertEqual(result.amount, Decimal("99.00"))

    @responses.activate
    def test_create_invoice_parses_decimal_and_aware_datetimes(self) -> None:
        invoice = deepcopy(VALID_INVOICE_JSON)
        invoice["paid_at"] = None
        responses.post(
            "https://testnet-pay.crypt.bot/api/createInvoice",
            json={"ok": True, "result": invoice},
        )

        result = self.client.create_invoice(
            amount=Decimal("99.00"),
            payload="0f57a4f1-1956-45be-8dc0-d891c00c74c1",
            description="MTProto на 30 дней",
        )

        self.assertEqual(result.amount, Decimal("99.00"))
        self.assertEqual(result.accepted_assets, frozenset({"USDT", "TON"}))
        self.assertTrue(timezone.is_aware(result.created_at))
        self.assertTrue(timezone.is_aware(result.expiration_date))
        self.assertIsNone(result.paid_at)

    @responses.activate
    def test_active_invoice_allows_omitted_paid_only_fields(self) -> None:
        invoice = deepcopy(VALID_INVOICE_JSON)
        invoice["status"] = "active"
        invoice.pop("paid_asset")
        invoice.pop("paid_at")
        responses.post(
            "https://testnet-pay.crypt.bot/api/createInvoice",
            json={"ok": True, "result": invoice},
        )

        try:
            result = self.client.create_invoice(
                amount=Decimal("99.00"),
                payload="0f57a4f1-1956-45be-8dc0-d891c00c74c1",
                description="MTProto на 30 дней",
            )
        except CryptoPayClientError as exc:
            self.fail(f"active invoice without paid fields was rejected: {exc}")

        self.assertIsNone(result.paid_asset)
        self.assertIsNone(result.paid_at)

    @responses.activate
    def test_get_invoices_sends_bounded_invoice_ids_and_maps_items(self) -> None:
        second_invoice = deepcopy(VALID_INVOICE_JSON)
        second_invoice["invoice_id"] = 732
        responses.get(
            "https://testnet-pay.crypt.bot/api/getInvoices",
            json={"ok": True, "result": {"items": [VALID_INVOICE_JSON, second_invoice]}},
        )

        result = self.client.get_invoices(invoice_ids=[731, 732])

        request = responses.calls[0].request
        self.assertEqual(request.headers["Crypto-Pay-API-Token"], "test-token")
        self.assertEqual(parse_qs(urlsplit(request.url).query), {"invoice_ids": ["731,732"]})
        self.assertEqual([invoice.invoice_id for invoice in result], [731, 732])

    @responses.activate
    def test_timeout_raises_crypto_pay_client_error_without_token_or_body(self) -> None:
        responses.post(
            "https://testnet-pay.crypt.bot/api/createInvoice",
            body=requests.Timeout("provider did not respond"),
        )

        with self.assertRaisesRegex(CryptoPayClientError, "^cryptopay_timeout$") as error:
            self.client.create_invoice(
                amount=Decimal("99.00"),
                payload="0f57a4f1-1956-45be-8dc0-d891c00c74c1",
                description="MTProto на 30 дней",
            )

        self.assertNotIn("test-token", str(error.exception))
        self.assertNotIn("0f57a4f1", str(error.exception))

    @responses.activate
    def test_ok_false_raises_safe_error(self) -> None:
        responses.post(
            "https://testnet-pay.crypt.bot/api/createInvoice",
            json={"ok": False, "error": {"name": "sensitive provider text"}},
        )

        with self.assertRaisesRegex(CryptoPayClientError, "^cryptopay_rejected$"):
            self.client.create_invoice(
                amount=Decimal("99.00"),
                payload="0f57a4f1-1956-45be-8dc0-d891c00c74c1",
                description="MTProto на 30 дней",
            )

    @responses.activate
    def test_malformed_result_raises_safe_error(self) -> None:
        responses.post(
            "https://testnet-pay.crypt.bot/api/createInvoice",
            json={"ok": True, "result": []},
        )

        with self.assertRaisesRegex(CryptoPayClientError, "^cryptopay_malformed$"):
            self.client.create_invoice(
                amount=Decimal("99.00"),
                payload="0f57a4f1-1956-45be-8dc0-d891c00c74c1",
                description="MTProto на 30 дней",
            )

    @responses.activate
    def test_non_object_envelope_raises_safe_malformed_error(self) -> None:
        for envelope in ([], None, "ok"):
            with self.subTest(envelope=envelope):
                responses.reset()
                if envelope is None:
                    responses.post(
                        "https://testnet-pay.crypt.bot/api/createInvoice",
                        body="null",
                    )
                else:
                    responses.post(
                        "https://testnet-pay.crypt.bot/api/createInvoice",
                        json=envelope,
                    )

                with self.assertRaisesRegex(CryptoPayClientError, "^cryptopay_malformed$"):
                    self.client.create_invoice(
                        amount=Decimal("99.00"),
                        payload="0f57a4f1-1956-45be-8dc0-d891c00c74c1",
                        description="MTProto на 30 дней",
                    )

    @responses.activate
    def test_malformed_provider_timestamps_raise_safe_error(self) -> None:
        for field, value in (
            ("created_at", 1_754_039_200),
            ("expiration_date", "2026-08-02T12:30:00"),
            ("paid_asset", 731),
            ("paid_at", "not-a-date"),
        ):
            with self.subTest(field=field):
                invoice = deepcopy(VALID_INVOICE_JSON)
                invoice[field] = value
                responses.reset()
                responses.post(
                    "https://testnet-pay.crypt.bot/api/createInvoice",
                    json={"ok": True, "result": invoice},
                )

                with self.assertRaisesRegex(CryptoPayClientError, "^cryptopay_malformed$"):
                    self.client.create_invoice(
                        amount=Decimal("99.00"),
                        payload="0f57a4f1-1956-45be-8dc0-d891c00c74c1",
                        description="MTProto на 30 дней",
                    )

    @responses.activate
    def test_connection_and_http_errors_raise_safe_unavailable_error(self) -> None:
        for body, status in ((requests.ConnectionError("unreachable"), 200), ("", 503)):
            with self.subTest(body=body, status=status):
                responses.reset()
                responses.post(
                    "https://testnet-pay.crypt.bot/api/createInvoice",
                    body=body,
                    status=status,
                )

                with self.assertRaisesRegex(CryptoPayClientError, "^cryptopay_unavailable$"):
                    self.client.create_invoice(
                        amount=Decimal("99.00"),
                        payload="0f57a4f1-1956-45be-8dc0-d891c00c74c1",
                        description="MTProto на 30 дней",
                    )

    def test_uses_configured_timeout_for_provider_request(self) -> None:
        response = Mock()
        response.json.return_value = {"ok": True, "result": VALID_INVOICE_JSON}
        with patch("apps.payments.clients.crypto_pay.requests.post", return_value=response) as request:
            self.client.create_invoice(
                amount=Decimal("99.00"),
                payload="0f57a4f1-1956-45be-8dc0-d891c00c74c1",
                description="MTProto на 30 дней",
            )

        self.assertEqual(request.call_args.kwargs["timeout"], 5.0)
