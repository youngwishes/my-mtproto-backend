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

    @mock.patch(
        "apps.core.decorators._log_infra_error", side_effect=Exception("tg down")
    )
    def test_infra_error_propagates_even_if_admin_notify_fails(self, _) -> None:
        with self.assertRaises(_InfraBoom):
            _Infra()()
