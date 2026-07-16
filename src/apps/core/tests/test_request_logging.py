from __future__ import annotations

import logging
from unittest import mock

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from config.middlewares import RequestLoggingMiddleware


class RequestLoggingMiddlewareTests(SimpleTestCase):
    def test_subscription_metric_has_status_latency_and_no_bearer_material(
        self,
    ) -> None:
        token = "secret-subscription-token"
        request = RequestFactory().get(
            f"/api/v1/vpn/subscriptions/{token}/?payload=raw",
            HTTP_AUTHORIZATION="Bearer secret-auth",
        )
        middleware = RequestLoggingMiddleware(lambda _: HttpResponse(status=429))

        with mock.patch("config.middlewares.emit_vpn_metric") as emit_metric:
            with mock.patch(
                "config.middlewares.time.monotonic", side_effect=(10.0, 10.125)
            ):
                with self.assertLogs(
                    "config.middlewares", level=logging.INFO
                ) as captured:
                    middleware(request)

        self.assertEqual(
            [call.args[0].name for call in emit_metric.call_args_list],
            [
                "vpn_subscription_requests_total",
                "vpn_subscription_latency_observed_ms",
                "vpn_subscription_rate_limited_total",
            ],
        )
        self.assertEqual(
            [call.args[0].value for call in emit_metric.call_args_list],
            [1, 125, 1],
        )

        output = " ".join(captured.output)
        self.assertIn("vpn_subscription_request", output)
        self.assertIn("'status': 429", output)
        self.assertIn("'latency_ms': 125", output)
        self.assertIn("'rate_limited': 1", output)
        for forbidden in (token, "payload=raw", "secret-auth", "Authorization"):
            self.assertNotIn(forbidden, output)

    def test_mutating_request_remains_fail_closed_and_redacted(self) -> None:
        request = RequestFactory().post(
            "/api/v1/vpn/bot/reissue/",
            data='{"desired_uuid": "secret"}',
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer secret-auth",
        )
        middleware = RequestLoggingMiddleware(lambda _: HttpResponse(status=200))

        with self.assertLogs("config.middlewares", level=logging.INFO) as captured:
            middleware(request)

        output = " ".join(captured.output)
        self.assertIn("[redacted]", output)
        self.assertNotIn("desired_uuid", output)
        self.assertNotIn("secret-auth", output)
