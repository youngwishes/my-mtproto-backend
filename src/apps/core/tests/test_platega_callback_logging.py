from __future__ import annotations

from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from config.middlewares import RequestLoggingMiddleware


_CALLBACK_PATH = "/api/v1/payments/platega/callback/"


class _BodyTrapRequest:
    path = _CALLBACK_PATH
    method = "POST"

    @property
    def body(self) -> bytes:
        raise AssertionError("middleware read the Platega callback body")


class TestPlategaCallbackMiddlewareBoundary(SimpleTestCase):
    def test_exact_callback_path_bypasses_body_access_and_logging(self) -> None:
        response = object()
        middleware = RequestLoggingMiddleware(
            lambda request: response,
        )

        with self.assertNoLogs("config.middlewares", level="INFO"):
            actual = middleware(_BodyTrapRequest())

        self.assertIs(actual, response)


@override_settings(
    PLATEGA_MERCHANT_ID="configured-merchant",
    PLATEGA_SECRET="configured-secret",
)
class TestPlategaCallbackLogging(APITestCase):
    def test_sensitive_callback_request_emits_no_middleware_log(self) -> None:
        with self.assertNoLogs("config.middlewares", level="INFO"):
            response = self.client.generic(
                "POST",
                _CALLBACK_PATH,
                b'{"private":"sensitive-callback-body"}',
                content_type="application/json",
                HTTP_X_MERCHANTID="sensitive-invalid-merchant",
                HTTP_X_SECRET="sensitive-callback-secret",
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
