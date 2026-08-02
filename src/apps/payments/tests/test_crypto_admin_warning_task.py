from __future__ import annotations

from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.payments import tasks


class TestWarnCryptoWebhookAdminTask(SimpleTestCase):
    @override_settings(MY_TELEGRAM_ID="900001", TELEGRAM_TIMEOUT=7)
    @mock.patch("apps.payments.tasks.send_telegram_message")
    def test_warning_transport_uses_only_allowlisted_fields(
        self,
        send: mock.Mock,
    ) -> None:
        warning = {
            "reason": "amount_mismatch",
            "update_id": 42,
            "invoice_id": 731,
            "intent_id": 9,
            "api_token": "test-api-token",
            "webhook_secret": "path-secret",
            "signature": "signature-value",
            "raw_body": 'raw-body:{"payload":"private-public-uuid"}',
            "telegram_id": "1487189460",
            "username": "private-username",
            "invoice_url": "https://t.me/CryptoBot?start=private",
            "gift_code": "KEY-ABCD-1234",
            "vpn_url": "https://vpn.example/subscription/secret",
        }

        tasks.warn_crypto_webhook_admin_task.run(warning)

        send.assert_called_once()
        self.assertEqual(send.call_args.kwargs["chat_id"], "900001")
        self.assertEqual(send.call_args.kwargs["timeout"], 7)
        text = send.call_args.kwargs["text"]
        for value in ("amount_mismatch", 42, 731, 9):
            self.assertIn(str(value), text)
        for forbidden in (
            "test-api-token",
            "path-secret",
            "signature-value",
            "raw-body",
            "private-public-uuid",
            "1487189460",
            "private-username",
            "https://t.me/CryptoBot",
            "KEY-ABCD-1234",
            "https://vpn.example/subscription/secret",
        ):
            self.assertNotIn(forbidden, text)
