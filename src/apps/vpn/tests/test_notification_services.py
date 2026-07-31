from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.notifications.models import NotificationTemplate
from apps.vpn.services import get_notify_vpn_expiry_service
from apps.vpn.tests.factories import VPNSubscriptionFactory


class TestNotifyVPNExpiryService(TestCase):
    @patch("apps.vpn.services.notify_vpn_expiry_service.send_telegram_message")
    def test_sends_day_notification_only_for_active_subscriptions_expiring_tomorrow(
        self,
        send_telegram_message,
    ) -> None:
        now = timezone.now().replace(hour=15, minute=0, second=0, microsecond=0)
        expected = VPNSubscriptionFactory(
            user__username="1001",
            expired_at=now + timedelta(days=1, hours=2),
        )
        VPNSubscriptionFactory(user__username="1002", expired_at=now + timedelta(hours=2))
        VPNSubscriptionFactory(
            user__username="1003",
            expired_at=now + timedelta(days=2, hours=2),
        )

        with patch("apps.vpn.services.notify_vpn_expiry_service.timezone.now", return_value=now):
            sent_count = get_notify_vpn_expiry_service()(window="day")

        self.assertEqual(sent_count, 1)
        send_telegram_message.assert_called_once()
        self.assertEqual(send_telegram_message.call_args.kwargs["chat_id"], int(expected.user.username))

    @patch("apps.vpn.services.notify_vpn_expiry_service.send_telegram_message")
    def test_sends_hour_notification_only_for_active_subscriptions_expiring_today(
        self,
        send_telegram_message,
    ) -> None:
        now = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)
        expected = VPNSubscriptionFactory(
            user__username="1004",
            expired_at=now + timedelta(hours=2),
        )
        VPNSubscriptionFactory(
            user__username="1005",
            expired_at=now + timedelta(days=1, hours=2),
        )
        VPNSubscriptionFactory(
            user__username="1006",
            is_active=False,
            expired_at=now + timedelta(hours=2),
        )

        with patch("apps.vpn.services.notify_vpn_expiry_service.timezone.now", return_value=now):
            sent_count = get_notify_vpn_expiry_service()(window="hour")

        self.assertEqual(sent_count, 1)
        self.assertEqual(send_telegram_message.call_args.kwargs["chat_id"], int(expected.user.username))

    @patch("apps.vpn.services.notify_vpn_expiry_service.send_telegram_message")
    def test_sends_expired_notification_only_after_subscription_is_deactivated(
        self,
        send_telegram_message,
    ) -> None:
        now = timezone.now()
        expected = VPNSubscriptionFactory(
            user__username="1007",
            is_active=False,
            expired_at=now - timedelta(minutes=10),
        )
        VPNSubscriptionFactory(user__username="1008", expired_at=now - timedelta(minutes=10))
        VPNSubscriptionFactory(
            user__username="1009",
            is_active=False,
            expired_at=now - timedelta(days=2),
        )

        with patch("apps.vpn.services.notify_vpn_expiry_service.timezone.now", return_value=now):
            sent_count = get_notify_vpn_expiry_service()(window="expired")

        self.assertEqual(sent_count, 1)
        self.assertEqual(send_telegram_message.call_args.kwargs["chat_id"], int(expected.user.username))

    def test_vpn_templates_use_vpn_callback_without_changing_mtproto_templates(self) -> None:
        for slug in ("vpn_before_expiry_1day", "vpn_before_expiry_1hour", "vpn_deactivated"):
            template = NotificationTemplate.objects.get(slug=slug)
            rendered = template.render()
            self.assertEqual(rendered.markup.keyboard[0][0].callback_data, "vpn")

        mtproto_template = NotificationTemplate.objects.get(slug="before_expiry_1day")
        self.assertNotEqual(mtproto_template.button_callback_data, "vpn")
