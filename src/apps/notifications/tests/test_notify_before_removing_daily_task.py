from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.notifications.tasks import notify_before_removing_daily
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory

_SERVICE_MODULE = "apps.notifications.services.notify_before_removing_daily_service"


class TestNotifyBeforeRemovingDailyTask(TestCase):
    def setUp(self):
        self.server = VDSInstanceFactory()
        self.user = SystemUserFactory(username="123456789")
        self.key = MTPRotoKeyFactory(user=self.user)

    @mock.patch(f"{_SERVICE_MODULE}.get_template")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_does_not_notify_when_key_expires_today(self, mock_send, mock_get_template) -> None:
        notify_before_removing_daily()
        self.assertEqual(mock_send.call_count, 0)

    @mock.patch(f"{_SERVICE_MODULE}.get_template")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_does_not_notify_when_key_expires_in_two_days(self, mock_send, mock_get_template) -> None:
        self.key.expired_date = timezone.now() + timedelta(days=2)
        self.key.save()
        notify_before_removing_daily()
        self.assertEqual(mock_send.call_count, 0)

    @mock.patch(f"{_SERVICE_MODULE}.time")
    @mock.patch(f"{_SERVICE_MODULE}.get_template")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_notifies_user_once_when_key_expires_tomorrow(self, mock_send, mock_get_template, _time) -> None:
        mock_rendered = mock.Mock()
        mock_rendered.text = "Your link expires soon"
        mock_rendered.markup = None
        mock_get_template.return_value.render.return_value = mock_rendered

        self.key.expired_date = timezone.now() + timedelta(days=1)
        self.key.save()
        notify_before_removing_daily()
        self.assertEqual(mock_send.call_count, 1)
        notify_before_removing_daily()
        self.assertEqual(mock_send.call_count, 1)  # user_notified flag prevents re-send
