from __future__ import annotations

from datetime import date
from unittest.mock import Mock, patch

from django.test import SimpleTestCase


class TestSendProjectServerPaymentReminderTask(SimpleTestCase):
    def test_delegates_with_local_date_and_has_bounded_retries(self) -> None:
        from apps.infrastructure.tasks import send_project_server_payment_reminder_task

        service = Mock()
        with (
            patch(
                "apps.infrastructure.tasks.get_project_server_payment_reminder_service",
                return_value=service,
            ) as factory,
            patch(
                "apps.infrastructure.tasks.timezone.localdate",
                return_value=date(2026, 8, 15),
            ),
        ):
            send_project_server_payment_reminder_task.run()

        factory.assert_called_once_with()
        service.assert_called_once_with(today=date(2026, 8, 15))
        self.assertEqual(send_project_server_payment_reminder_task.max_retries, 3)

    def test_retries_any_exception_after_thirty_seconds(self) -> None:
        from apps.infrastructure.tasks import send_project_server_payment_reminder_task

        original_error = ValueError("telegram unavailable")
        retry_signal = RuntimeError("retry requested")
        service = Mock(side_effect=original_error)
        with (
            patch(
                "apps.infrastructure.tasks.get_project_server_payment_reminder_service",
                return_value=service,
            ),
            patch.object(
                send_project_server_payment_reminder_task,
                "retry",
                side_effect=retry_signal,
            ) as retry,
            self.assertRaisesRegex(RuntimeError, "retry requested"),
        ):
            send_project_server_payment_reminder_task.run()

        retry.assert_called_once_with(exc=original_error, countdown=30)
