from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.payments.services.notify_payment_service import get_notify_payment_service
from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestNotifyPaymentService(TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory()
        self.vds = VDSInstanceFactory()
        self.service = get_notify_payment_service()

    @mock.patch("apps.core.bot.TelegramBot.send_proxy_link")
    def test_sends_proxy_link_to_user(self, mock_send: mock.Mock) -> None:
        key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() + timedelta(days=30),
            was_deleted=False,
        )

        self.service(user=self.user, key=key)

        mock_send.assert_called_once_with(
            chat_id=self.user.username,
            link=key.get_proxy_link(),
        )
