from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.notifications.services import get_notify_before_removing_daily_service
from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory

_SERVICE_MODULE = "apps.notifications.services.notify_before_removing_daily_service"


class TestNotifyBeforeRemovingDailyService(TestCase):
    def setUp(self):
        self.server = VDSInstanceFactory()
        self.user = SystemUserFactory(username="123456789")
        self.key = MTPRotoKeyFactory(user=self.user)

    @mock.patch(f"{_SERVICE_MODULE}.get_template")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_does_not_notify_when_key_expires_today(self, mock_send, _get_template) -> None:
        get_notify_before_removing_daily_service()()
        mock_send.assert_not_called()

    @mock.patch(f"{_SERVICE_MODULE}.time")
    @mock.patch(f"{_SERVICE_MODULE}.get_template")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_notifies_user_for_key_expiring_tomorrow(self, mock_send, mock_get_template, _time) -> None:
        mock_rendered = mock.Mock()
        mock_rendered.text = "Your link expires soon"
        mock_rendered.markup = None
        mock_get_template.return_value.render.return_value = mock_rendered

        self.key.expired_date = timezone.now() + timedelta(days=1)
        self.key.save()

        get_notify_before_removing_daily_service()()

        mock_send.assert_called_once_with(
            chat_id=int(self.user.username),
            text=mock_rendered.text,
            markup=mock_rendered.markup,
        )

    @mock.patch(f"{_SERVICE_MODULE}.time")
    @mock.patch(f"{_SERVICE_MODULE}.get_template")
    @mock.patch(f"{_SERVICE_MODULE}.log_service_error")
    def test_notifies_admin_on_error_and_continues(self, mock_notify, mock_get_template, _time) -> None:
        second_user = SystemUserFactory(username="987654321")
        second_key = MTPRotoKeyFactory(
            user=second_user,
            expired_date=timezone.now() + timedelta(days=1),
        )
        self.key.expired_date = timezone.now() + timedelta(days=1)
        self.key.save()

        mock_get_template.return_value.render.side_effect = Exception("send failed")

        get_notify_before_removing_daily_service()()

        self.assertEqual(mock_notify.call_count, 2)
