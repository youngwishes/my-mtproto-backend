from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.notifications.tasks import broadcast_proxy_links_task
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestBroadcastProxyLinksTask(TestCase):
    def setUp(self):
        self.server = VDSInstanceFactory()
        self.user = SystemUserFactory(first_month_free_used=True, username="123456789")
        self.expired_date = timezone.now() + timedelta(days=10)
        self.key = MTPRotoKeyFactory(
            user=self.user,
            expired_date=self.expired_date,
        )

    @mock.patch("apps.notifications.services.broadcast_proxy_links_service.send_telegram_message")
    def test_sends_message_and_extends_key(self, mock_send):
        broadcast_proxy_links_task()

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["chat_id"], int(self.user.username))
        self.assertIn("markup", call_kwargs)

        self.key.refresh_from_db()
        self.assertAlmostEqual(
            self.key.expired_date,
            self.expired_date + timedelta(days=3),
            delta=timedelta(seconds=5),
        )

    @mock.patch("apps.notifications.services.broadcast_proxy_links_service.send_telegram_message")
    def test_skips_users_without_first_month_free(self, mock_send):
        user_no_free = SystemUserFactory(first_month_free_used=False, username="987654321")
        MTPRotoKeyFactory(
            user=user_no_free,
            expired_date=timezone.now() + timedelta(days=10),
        )

        broadcast_proxy_links_task()

        self.assertEqual(mock_send.call_count, 1)
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["chat_id"], int(self.user.username))

    @mock.patch("apps.notifications.services.broadcast_proxy_links_service.send_telegram_message")
    def test_skips_inactive_keys(self, mock_send):
        self.key.is_active = False
        self.key.save(update_fields=["is_active"])

        broadcast_proxy_links_task()

        mock_send.assert_not_called()

    @mock.patch("apps.notifications.services.broadcast_proxy_links_service.send_telegram_message")
    def test_skips_deleted_keys(self, mock_send):
        self.key.was_deleted = True
        self.key.save(update_fields=["was_deleted"])

        broadcast_proxy_links_task()

        mock_send.assert_not_called()

    @mock.patch("apps.notifications.services.broadcast_proxy_links_service.send_telegram_message")
    def test_skips_expired_keys(self, mock_send):
        self.key.expired_date = timezone.now() - timedelta(days=1)
        self.key.save(update_fields=["expired_date"])

        broadcast_proxy_links_task()

        mock_send.assert_not_called()

    @mock.patch("apps.notifications.services.broadcast_proxy_links_service.send_telegram_message")
    def test_does_not_extend_on_telegram_error(self, mock_send):
        mock_send.side_effect = [Exception("Telegram API error"), None]

        broadcast_proxy_links_task()

        self.key.refresh_from_db()
        self.assertEqual(self.key.expired_date, self.expired_date)

    @mock.patch("apps.notifications.services.broadcast_proxy_links_service.send_telegram_message")
    def test_notifies_admin_on_error(self, mock_send):
        mock_send.side_effect = [Exception("Telegram API error"), None]

        broadcast_proxy_links_task()

        self.assertEqual(mock_send.call_count, 2)
        admin_call_kwargs = mock_send.call_args_list[1].kwargs
        self.assertIn("Системное оповещение", admin_call_kwargs["text"])

    @mock.patch("apps.notifications.services.broadcast_proxy_links_service.send_telegram_message")
    def test_sends_to_multiple_users(self, mock_send):
        user2 = SystemUserFactory(first_month_free_used=True, username="555555555")
        key2 = MTPRotoKeyFactory(
            user=user2,
            expired_date=timezone.now() + timedelta(days=5),
        )

        broadcast_proxy_links_task()

        self.assertEqual(mock_send.call_count, 2)
        self.key.refresh_from_db()
        key2.refresh_from_db()
        self.assertAlmostEqual(
            self.key.expired_date,
            self.expired_date + timedelta(days=3),
            delta=timedelta(seconds=5),
        )
        self.assertAlmostEqual(
            key2.expired_date,
            timezone.now() + timedelta(days=5) + timedelta(days=3),
            delta=timedelta(seconds=5),
        )

    @mock.patch("apps.notifications.services.broadcast_proxy_links_service.send_telegram_message")
    def test_continues_after_error_for_one_user(self, mock_send):
        user2 = SystemUserFactory(first_month_free_used=True, username="444444444")
        key2_expired = timezone.now() + timedelta(days=5)
        key2 = MTPRotoKeyFactory(
            user=user2,
            expired_date=key2_expired,
        )

        mock_send.side_effect = [Exception("blocked by user"), None, None]

        broadcast_proxy_links_task()

        self.key.refresh_from_db()
        self.assertAlmostEqual(
            self.key.expired_date,
            self.expired_date,
            delta=timedelta(seconds=5),
        )

        key2.refresh_from_db()
        self.assertAlmostEqual(
            key2.expired_date,
            key2_expired + timedelta(days=3),
            delta=timedelta(seconds=5),
        )
