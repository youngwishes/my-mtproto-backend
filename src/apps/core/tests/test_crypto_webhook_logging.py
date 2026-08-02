from __future__ import annotations

from django.test import override_settings
from rest_framework.test import APITestCase


@override_settings(
    CRYPTOPAY_API_TOKEN="test-api-token",
    CRYPTOPAY_WEBHOOK_SECRET="path-secret",
)
class TestCryptoWebhookLogging(APITestCase):
    def test_webhook_log_omits_path_secret_headers_and_body(self) -> None:
        with (
            self.assertLogs("config.middlewares", level="INFO") as captured,
            self.assertLogs("django.request", level="WARNING") as request_logs,
        ):
            self.client.generic(
                "POST",
                "/api/v1/payments/crypto/webhooks/path-secret/",
                b'{"payload":"private-raw-body"}',
                content_type="application/json",
                HTTP_CRYPTO_PAY_API_SIGNATURE="private-signature",
            )

        self.assertEqual(
            captured.records[0].msg,
            {
                "method": "POST",
                "path": "/api/v1/payments/crypto/webhooks/[REDACTED]/",
            },
        )
        log = "\n".join(captured.output)
        for forbidden in (
            "path-secret",
            "private-signature",
            "private-raw-body",
            "headers",
            "body",
        ):
            self.assertNotIn(forbidden, log)
        self.assertNotIn("path-secret", "\n".join(request_logs.output))
        self.assertIn("[REDACTED]", "\n".join(request_logs.output))

    def test_non_webhook_post_keeps_headers_and_decoded_body(self) -> None:
        with self.assertLogs("config.middlewares", level="INFO") as captured:
            self.client.generic(
                "POST",
                "/ordinary-path/",
                b'{"visible":"ordinary-body"}',
                content_type="application/json",
                HTTP_X_REQUEST_CONTEXT="ordinary-header",
            )

        logged = captured.records[0].msg
        self.assertEqual(logged["method"], "POST")
        self.assertEqual(logged["path"], "/ordinary-path/")
        self.assertEqual(logged["body"], {"visible": "ordinary-body"})
        self.assertEqual(logged["headers"]["X-Request-Context"], "ordinary-header")
