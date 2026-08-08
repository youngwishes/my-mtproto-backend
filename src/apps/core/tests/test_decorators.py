from __future__ import annotations

from unittest import mock

from django.test import TestCase

from apps.core.decorators import log_infra_error, log_service_error
from apps.core.exceptions import BaseInfraError, BaseServiceError


class _Boom(BaseServiceError):
    """boom"""


class _InfraBoom(BaseInfraError):
    """infra boom"""


class _Service:
    @log_service_error
    def __call__(self, **kwargs):
        raise _Boom(telegram_id="1")


class _StrictService:
    def __init__(self) -> None:
        self.received_value: str | None = None

    @log_service_error
    def __call__(self, *, value: str) -> None:
        self.received_value = value
        raise _Boom(telegram_id="123456")


class _Infra:
    @log_infra_error
    def __call__(self, **kwargs):
        raise _InfraBoom(telegram_id="1")


class TestDecoratorsNotificationGuard(TestCase):
    """Сбой Telegram-нотификации не должен подменять доменную ошибку на 500."""

    @mock.patch(
        "apps.core.decorators._log_service_error", side_effect=Exception("tg down")
    )
    def test_service_error_propagates_even_if_notification_fails(self, _) -> None:
        with self.assertRaises(_Boom):
            _Service()()

    @mock.patch("apps.core.decorators._log_service_error")
    def test_service_error_logs_by_default_and_passes_only_domain_kwargs(
        self,
        error_logger: mock.Mock,
    ) -> None:
        service = _StrictService()

        with self.assertRaises(_Boom):
            service(value="domain-value")

        self.assertEqual(service.received_value, "domain-value")
        error_logger.assert_called_once()

    @mock.patch("apps.core.decorators._log_service_error")
    def test_notify_false_suppresses_log_and_is_not_forwarded(
        self,
        error_logger: mock.Mock,
    ) -> None:
        service = _StrictService()

        with self.assertRaises(_Boom):
            service(value="domain-value", notify_on_error=False)

        self.assertEqual(service.received_value, "domain-value")
        error_logger.assert_not_called()

    @mock.patch(
        "apps.core.decorators._log_infra_error", side_effect=Exception("tg down")
    )
    def test_infra_error_propagates_even_if_admin_notify_fails(self, _) -> None:
        with self.assertRaises(_InfraBoom):
            _Infra()()
