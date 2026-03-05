from datetime import timedelta
from unittest import mock

import responses
from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vds.tasks import notify_before_removing_daily
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestNotifyUserTask(TestCase):
    def setUp(self):
        self.server = VDSInstanceFactory()
        self.user = SystemUserFactory()
        self.key = MTPRotoKeyFactory(user=self.user, vds=self.server)

    @mock.patch("apps.core.bot.TelegramBot.notify_before_removing")
    def test_notify_user_task_case1(self, notify) -> None:
        notify_before_removing_daily()
        self.assertEqual(notify.call_count, 0)

    @mock.patch("apps.core.bot.TelegramBot.notify_before_removing")
    def test_notify_user_task_case2(self, notify) -> None:
        self.key.expired_date = timezone.now() + timedelta(days=2)
        self.key.save()
        notify_before_removing_daily()
        self.assertEqual(notify.call_count, 0)

    @mock.patch("apps.core.bot.TelegramBot.notify_before_removing")
    def test_notify_user_task_case3(self, notify) -> None:
        self.key.expired_date = timezone.now() + timedelta(days=1)
        self.key.save()
        notify_before_removing_daily()
        self.assertEqual(notify.call_count, 1)
        notify_before_removing_daily()
        self.assertEqual(notify.call_count, 1)
