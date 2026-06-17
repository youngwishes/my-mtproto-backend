from __future__ import annotations

from unittest import mock

from django.test import TestCase, override_settings

from apps.core.exceptions import BaseInfraError, BaseServiceError


class TestLogInfraError(TestCase):
    @mock.patch("apps.core.telegram.error_logger.send_telegram_message")
    @override_settings(
        MY_TELEGRAM_ID=999, TELEGRAM_TIMEOUT=5, ERROR_NOTIFICATIONS_ENABLED=True
    )
    def test_sends_red_error_to_admin(self, mock_send: mock.Mock) -> None:
        from apps.core.telegram.error_logger import log_infra_error

        exc = BaseInfraError(telegram_id=123, message="VDS down")
        log_infra_error(exc)

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        self.assertEqual(call_kwargs.kwargs["chat_id"], 999)
        self.assertIn("🔴", call_kwargs.kwargs["text"])
        self.assertIn("SERVER INTERNAL ERROR (500)", call_kwargs.kwargs["text"])
        self.assertIn("VDS down", call_kwargs.kwargs["text"])
        self.assertEqual(call_kwargs.kwargs["timeout"], 5)


class TestLogServiceError(TestCase):
    @mock.patch("apps.core.telegram.error_logger.send_telegram_message")
    @override_settings(
        MY_TELEGRAM_ID=999, TELEGRAM_TIMEOUT=5, ERROR_NOTIFICATIONS_ENABLED=True
    )
    def test_sends_yellow_error_to_admin(self, mock_send: mock.Mock) -> None:
        from apps.core.telegram.error_logger import log_service_error

        exc = BaseServiceError(telegram_id=456, message="Product not found")
        log_service_error(exc)

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        self.assertEqual(call_kwargs.kwargs["chat_id"], 999)
        self.assertIn("🟡", call_kwargs.kwargs["text"])
        self.assertIn("SERVICE (400)", call_kwargs.kwargs["text"])
        self.assertIn("Product not found", call_kwargs.kwargs["text"])


class TestErrorNotificationsToggle(TestCase):
    """Флаг ERROR_NOTIFICATIONS_ENABLED глушит админ-оповещения (локально/в e2e)."""

    @mock.patch("apps.core.telegram.error_logger.send_telegram_message")
    @override_settings(ERROR_NOTIFICATIONS_ENABLED=False, MY_TELEGRAM_ID=999)
    def test_service_error_not_sent_when_disabled(self, mock_send: mock.Mock) -> None:
        from apps.core.telegram.error_logger import log_service_error

        log_service_error(BaseServiceError(telegram_id=1, message="x"))

        mock_send.assert_not_called()

    @mock.patch("apps.core.telegram.error_logger.send_telegram_message")
    @override_settings(ERROR_NOTIFICATIONS_ENABLED=False, MY_TELEGRAM_ID=999)
    def test_infra_error_not_sent_when_disabled(self, mock_send: mock.Mock) -> None:
        from apps.core.telegram.error_logger import log_infra_error

        log_infra_error(BaseInfraError(telegram_id=1, message="x"))

        mock_send.assert_not_called()
