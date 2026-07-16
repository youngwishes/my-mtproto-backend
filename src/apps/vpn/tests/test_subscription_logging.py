from __future__ import annotations

import copy
import io
import logging
import logging.config
from contextlib import redirect_stderr

from django.core import mail
from django.test import RequestFactory, SimpleTestCase, override_settings

from config.settings.logging_conf import build_production_logging


class VPNSubscriptionLoggingTest(SimpleTestCase):
    @override_settings(
        DEBUG=False,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        ADMINS=(("Ops", "ops@example.com"),),
        SERVER_EMAIL="server@example.com",
    )
    def test_production_django_5xx_topology_redacts_console_and_admin_email(self) -> None:
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
                topology = production_logging["loggers"][logger_name]
                self.assertFalse(topology["propagate"])
                self.assertEqual(topology["handlers"], ["console", "mail_admins"])
                mail.outbox.clear()
