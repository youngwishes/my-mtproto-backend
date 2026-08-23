from __future__ import annotations

from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.users.services.dtos import IssuedKeyOut
from apps.users.tasks import grant_daily_free_trials_task, send_free_link_to_user_task
from apps.users.tests.factories import SystemUserFactory


class TestGrantDailyFreeTrialsTask(SimpleTestCase):
    @mock.patch("apps.users.services.get_daily_free_trial_grant_service")
    def test_delegates_to_service_from_factory(self, factory) -> None:
        service = factory.return_value

        grant_daily_free_trials_task()

        factory.assert_called_once_with()
        service.assert_called_once_with()


class TestSendFreeLinkToUserTask(TestCase):
    @mock.patch("apps.users.tasks.time.sleep")
    @mock.patch("apps.users.tasks.send_telegram_message")
    @mock.patch("apps.users.tasks.get_first_free_link_service")
    def test_notification_expiry_uses_full_human_date(
        self,
        service_factory: mock.Mock,
        send: mock.Mock,
        _sleep: mock.Mock,
    ) -> None:
        user = SystemUserFactory(username="100500", first_month_free_used=False)
        service_factory.return_value.return_value = IssuedKeyOut(
            expired_date="10.08.26",
        )

        send_free_link_to_user_task.run([user.username])

        text = send.call_args.kwargs["text"]
        self.assertIn("10.08.2026", text)
        self.assertNotIn("10.08.26", text)
