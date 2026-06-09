from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory

_SERVICE_MODULE = "apps.notifications.services.broadcast_proxy_links_service"


class TestBroadcastProxyLinksService(TestCase):
    def setUp(self):
        self.server = VDSInstanceFactory()
        self.user = SystemUserFactory(username="123456789")
        self.key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.server,
            is_active=True,
            was_deleted=False,
            expired_date=timezone.now() + timedelta(days=10),
        )
        self.user.first_month_free_used = True
        self.user.save()

    def _get_service(self):
        from apps.notifications.services.broadcast_proxy_links_service import get_broadcast_proxy_links_service

        return get_broadcast_proxy_links_service()

    @mock.patch(f"{_SERVICE_MODULE}.time")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_does_not_send_when_no_broadcast_keys(self, mock_send, _time) -> None:
        self.key.is_active = False
        self.key.save()

        self._get_service()()

        mock_send.assert_not_called()

    @mock.patch(f"{_SERVICE_MODULE}.time")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_sends_message_to_user_with_proxy_link(self, mock_send, _time) -> None:
        self._get_service()()

        self.assertEqual(mock_send.call_count, 1)
        call_kwargs = mock_send.call_args
        self.assertEqual(call_kwargs.kwargs["chat_id"], int(self.user.username))

    @mock.patch(f"{_SERVICE_MODULE}.time")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_extends_key_expiry_by_3_days_after_sending(self, mock_send, _time) -> None:
        original_expiry = self.key.expired_date

        self._get_service()()

        self.key.refresh_from_db()
        self.assertEqual(self.key.expired_date, original_expiry + timedelta(days=3))

    @mock.patch(f"{_SERVICE_MODULE}.time")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_notifies_admin_on_error_and_continues_with_next_key(self, mock_send, _time) -> None:
        second_user = SystemUserFactory(username="987654321")
        second_user.first_month_free_used = True
        second_user.save()
        MTPRotoKeyFactory(
            user=second_user,
            vds=self.server,
            is_active=True,
            was_deleted=False,
            expired_date=timezone.now() + timedelta(days=10),
        )

        mock_send.side_effect = [Exception("telegram error"), None, None]

        self._get_service()()

        self.assertEqual(mock_send.call_count, 3)

    @mock.patch(f"{_SERVICE_MODULE}.time")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_failed_key_expiry_not_extended_on_error(self, mock_send, _time) -> None:
        original_expiry = self.key.expired_date
        mock_send.side_effect = Exception("telegram error")

        self._get_service()()

        self.key.refresh_from_db()
        self.assertEqual(self.key.expired_date, original_expiry)
