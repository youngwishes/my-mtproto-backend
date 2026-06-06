from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vds.tasks import notify_before_removing_daily
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestNotifyUserTask(TestCase):
    def setUp(self):
        self.server = VDSInstanceFactory()
        self.user = SystemUserFactory(username="123456789")
        self.key = MTPRotoKeyFactory(user=self.user, vds=self.server)

    @mock.patch("apps.vds.tasks.get_template")
    @mock.patch("apps.vds.tasks.send_telegram_message")
    def test_notify_user_task_case1(self, mock_send, mock_get_template) -> None:
        notify_before_removing_daily()
        self.assertEqual(mock_send.call_count, 0)

    @mock.patch("apps.vds.tasks.get_template")
    @mock.patch("apps.vds.tasks.send_telegram_message")
    def test_notify_user_task_case2(self, mock_send, mock_get_template) -> None:
        self.key.expired_date = timezone.now() + timedelta(days=2)
        self.key.save()
        notify_before_removing_daily()
        self.assertEqual(mock_send.call_count, 0)

    @mock.patch("apps.vds.tasks.time.sleep")
    @mock.patch("apps.vds.tasks.get_template")
    @mock.patch("apps.vds.tasks.send_telegram_message")
    def test_notify_user_task_case3(self, mock_send, mock_get_template, _sleep) -> None:
        mock_rendered = mock.Mock()
        mock_rendered.text = "Your link expires soon"
        mock_rendered.markup = None
        mock_get_template.return_value.render.return_value = mock_rendered

        self.key.expired_date = timezone.now() + timedelta(days=1)
        self.key.save()
        notify_before_removing_daily()
        self.assertEqual(mock_send.call_count, 1)
        notify_before_removing_daily()
        self.assertEqual(mock_send.call_count, 1)
