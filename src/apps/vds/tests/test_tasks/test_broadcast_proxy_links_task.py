from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import MTPRotoKey
from apps.vds.tasks import broadcast_proxy_links_task
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestBroadcastProxyLinksTask(TestCase):
    def setUp(self):
        self.server = VDSInstanceFactory()
        self.user = SystemUserFactory(first_month_free_used=True)
        self.expired_date = timezone.now() + timedelta(days=10)
        self.key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.server,
            expired_date=self.expired_date,
        )

    @mock.patch("apps.vds.tasks.bot")
    def test_sends_message_and_extends_key(self, mock_bot):
        broadcast_proxy_links_task()

        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args.kwargs
        self.assertEqual(call_kwargs["chat_id"], self.user.username)
        self.assertEqual(call_kwargs["parse_mode"], "HTML")
        self.assertIn("reply_markup", call_kwargs)

        self.key.refresh_from_db()
        self.assertAlmostEqual(
            self.key.expired_date,
            self.expired_date + timedelta(days=3),
            delta=timedelta(seconds=5),
        )

    @mock.patch("apps.vds.tasks.bot")
    def test_skips_users_without_first_month_free(self, mock_bot):
        user_no_free = SystemUserFactory(first_month_free_used=False)
        MTPRotoKeyFactory(
            user=user_no_free,
            vds=self.server,
            expired_date=timezone.now() + timedelta(days=10),
        )

        broadcast_proxy_links_task()

        self.assertEqual(mock_bot.send_message.call_count, 1)
        call_kwargs = mock_bot.send_message.call_args.kwargs
        self.assertEqual(call_kwargs["chat_id"], self.user.username)

    @mock.patch("apps.vds.tasks.bot")
    def test_skips_inactive_keys(self, mock_bot):
        self.key.is_active = False
        self.key.save(update_fields=["is_active"])

        broadcast_proxy_links_task()

        mock_bot.send_message.assert_not_called()

    @mock.patch("apps.vds.tasks.bot")
    def test_skips_deleted_keys(self, mock_bot):
        self.key.was_deleted = True
        self.key.save(update_fields=["was_deleted"])

        broadcast_proxy_links_task()

        mock_bot.send_message.assert_not_called()

    @mock.patch("apps.vds.tasks.bot")
    def test_skips_expired_keys(self, mock_bot):
        self.key.expired_date = timezone.now() - timedelta(days=1)
        self.key.save(update_fields=["expired_date"])

        broadcast_proxy_links_task()

        mock_bot.send_message.assert_not_called()

    @mock.patch("apps.vds.tasks.bot")
    def test_does_not_extend_on_telegram_error(self, mock_bot):
        mock_bot.send_message.side_effect = [
            Exception("Telegram API error"),
            None,
        ]

        broadcast_proxy_links_task()

        self.key.refresh_from_db()
        self.assertAlmostEqual(
            self.key.expired_date,
            self.expired_date,
            delta=timedelta(seconds=5),
        )

    @mock.patch("apps.vds.tasks.bot")
    def test_notifies_admin_on_error(self, mock_bot):
        mock_bot.send_message.side_effect = [
            Exception("Telegram API error"),
            None,
        ]

        broadcast_proxy_links_task()

        self.assertEqual(mock_bot.send_message.call_count, 2)
        admin_call_kwargs = mock_bot.send_message.call_args_list[1].kwargs
        self.assertIn("Системное оповещение", admin_call_kwargs["text"])

    @mock.patch("apps.vds.tasks.bot")
    def test_sends_to_multiple_users(self, mock_bot):
        user2 = SystemUserFactory(first_month_free_used=True)
        key2 = MTPRotoKeyFactory(
            user=user2,
            vds=self.server,
            expired_date=timezone.now() + timedelta(days=5),
        )

        broadcast_proxy_links_task()

        self.assertEqual(mock_bot.send_message.call_count, 2)
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

    @mock.patch("apps.vds.tasks.bot")
    def test_continues_after_error_for_one_user(self, mock_bot):
        user2 = SystemUserFactory(first_month_free_used=True)
        key2_expired = timezone.now() + timedelta(days=5)
        key2 = MTPRotoKeyFactory(
            user=user2,
            vds=self.server,
            expired_date=key2_expired,
        )

        mock_bot.send_message.side_effect = [
            Exception("blocked by user"),
            None,
            None,
        ]

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
