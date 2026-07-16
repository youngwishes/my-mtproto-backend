from __future__ import annotations

import copy
import io
import logging
import logging.config
import sys
from contextlib import redirect_stderr

from django.core import mail
from django.test import RequestFactory, SimpleTestCase, override_settings

from config.settings.logging_conf import build_production_logging
from config.logging_filters import SubscriptionPathRedactionFilter


class VPNSubscriptionLoggingTest(SimpleTestCase):
    def test_fail_closed_key_classifier_covers_aliases_components_and_prefixes(self) -> None:
        original = {
            "event": "vpn_metric",
            "status": 429,
            "value": 7,
            "latency_ms": 125,
            "nested": {
                "HTTP_AUTHORIZATION": "Token http-auth-secret",
                "HTTP_BOT_AUTH_TOKEN": "bot-auth-secret",
                "Bot-Auth-Token": "bot-header-secret",
                "access_token": "access-secret",
                "customerSubscriptionTokenValue": "subscription-secret",
                "Provider.Payload.Data": {"secret": "provider-secret"},
                "snapshot-payload-body": ["snapshot-secret"],
                "request.raw-uri": "https://example.test/raw-secret",
                "HTTP_QUERY_STRING": "token=query-secret",
                "requestBodyBytes": b"body-secret",
            },
            "message": "upstream replied Token non-bearer-secret",
        }
        pristine = copy.deepcopy(original)
        record = logging.LogRecord(
            name="apps.vpn.observability",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg=original,
            args=(),
            exc_info=None,
        )

        sanitized = SubscriptionPathRedactionFilter().filter(record)

        self.assertEqual(original, pristine)
        self.assertEqual(sanitized.msg["event"], "vpn_metric")
        self.assertEqual(sanitized.msg["status"], 429)
        self.assertEqual(sanitized.msg["value"], 7)
        self.assertEqual(sanitized.msg["latency_ms"], 125)
        rendered = repr(sanitized.msg)
        for forbidden in (
            "http-auth-secret",
            "bot-auth-secret",
            "bot-header-secret",
            "access-secret",
            "subscription-secret",
            "provider-secret",
            "snapshot-secret",
            "raw-secret",
            "query-secret",
            "body-secret",
            "non-bearer-secret",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_filter_returns_sanitized_copy_without_mutating_record_request_or_exception(
        self,
    ) -> None:
        token = "original-subscription-secret"
        request = RequestFactory().post(
            f"/api/v1/vpn/subscriptions/{token}/?token={token}",
            data={"body": "original-body-secret"},
            HTTP_AUTHORIZATION="Bearer original-auth-secret",
        )
        original_payload = {
            "nested": {
                "subscription_token": token,
                "provider_payload": {"secret": "provider-secret"},
                "snapshot_body": ["snapshot-secret"],
                "raw_uri": f"vless://{token}@example.test",
            }
        }
        try:
            raise RuntimeError(f"failed Authorization=Bearer {token}")
        except RuntimeError:
            original_exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="django.request",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg=original_payload,
            args=(),
            exc_info=original_exc_info,
        )
        record.request = request

        sanitized = SubscriptionPathRedactionFilter().filter(record)

        self.assertIsNot(sanitized, record)
        self.assertIs(record.msg, original_payload)
        self.assertIs(record.request, request)
        self.assertIs(record.exc_info, original_exc_info)
        self.assertEqual(request.path, f"/api/v1/vpn/subscriptions/{token}/")
        self.assertEqual(
            request.META["HTTP_AUTHORIZATION"], "Bearer original-auth-secret"
        )
        self.assertIn(b"original-body-secret", request.body)
        rendered = (
            repr(sanitized.msg)
            + repr(sanitized.request.META)
            + str(sanitized.exc_info[1])
        )
        for forbidden in (
            token,
            "original-auth-secret",
            "original-body-secret",
            "provider-secret",
            "snapshot-secret",
            "vless://",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_operational_filter_redacts_vless_auth_uuid_and_payload_material(
        self,
    ) -> None:
        stream = io.StringIO()
        with redirect_stderr(stream):
            logging.config.dictConfig(copy.deepcopy(build_production_logging()))
            logging.getLogger("apps.vpn.observability").error(
                "failed Authorization=Bearer top-secret "
                "vless://123e4567-e89b-12d3-a456-426614174000@example.test "
                'provider_data={"receipt":"secret"} snapshot={"accesses":["secret"]}'
            )
            logging.getLogger("apps.vpn.observability").error(
                {
                    "Authorization": "Bearer structured-secret",
                    "provider_data": {"receipt": "structured-receipt"},
                    "snapshot": {"accesses": ["structured-access"]},
                }
            )

        output = stream.getvalue()
        for forbidden in (
            "top-secret",
            "Authorization",
            "vless://",
            "123e4567-e89b-12d3-a456-426614174000",
            '"receipt":"secret"',
            '"accesses":["secret"]',
            "structured-secret",
            "structured-receipt",
            "structured-access",
        ):
            self.assertNotIn(forbidden, output)

    @override_settings(
        DEBUG=False,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        ADMINS=(("Ops", "ops@example.com"),),
        SERVER_EMAIL="server@example.com",
    )
    def test_production_django_5xx_topology_redacts_console_and_admin_email(
        self,
    ) -> None:
        for logger_name in ("django.request", "django.server"):
            with self.subTest(logger=logger_name):
                token = f"raw-secret-{logger_name.replace('.', '-')}"
                path = f"/api/v1/vpn/subscriptions/{token}/"
                request = RequestFactory().get(path, {"token": token})
                self.assertEqual(request.GET["token"], token)
                request.META.update(
                    REQUEST_URI=f"{path}?token={token}",
                    QUERY_STRING=f"token={token}",
                    SERVER_NAME="testserver",
                    SERVER_PORT="443",
                    REQUEST_METHOD="GET",
                )
                stream = io.StringIO()
                with redirect_stderr(stream):
                    production_logging = build_production_logging()
                    logging.config.dictConfig(copy.deepcopy(production_logging))
                    logger = logging.getLogger(logger_name)
                    try:
                        raise RuntimeError(f"failed at {request.path}")
                    except RuntimeError:
                        logger.error(
                            "Internal Server Error: %s",
                            request.path,
                            exc_info=True,
                            extra={"request": request, "status_code": 500},
                        )
                output = stream.getvalue() + "\n".join(
                    message.body for message in mail.outbox
                )
                self.assertNotIn(token, output)
                self.assertIn("/api/v1/vpn/subscriptions/:token/", output)
                self.assertEqual(request.path, path)
                self.assertEqual(request.GET["token"], token)
                self.assertEqual(request.META["REQUEST_URI"], f"{path}?token={token}")
                topology = production_logging["loggers"][logger_name]
                self.assertFalse(topology["propagate"])
                self.assertEqual(topology["handlers"], ["console", "mail_admins"])
                mail.outbox.clear()
