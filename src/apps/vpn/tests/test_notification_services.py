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
    def test_sends_day_notification_only_in_exact_24_hour_five_minute_window(
        self,
        send_telegram_message,
    ) -> None:
        now = timezone.now()
        starts_at = now + timedelta(hours=24)
        expected = VPNSubscriptionFactory(user__username="1001", expired_at=starts_at)
        VPNSubscriptionFactory(
            user__username="1002",
            expired_at=starts_at - timedelta(microseconds=1),
        )
        VPNSubscriptionFactory(
            user__username="1003",
            expired_at=starts_at + timedelta(minutes=5),
        )

        with patch("apps.vpn.services.notify_vpn_expiry_service.timezone.now", return_value=now):
            sent_count = get_notify_vpn_expiry_service()(window="day")

        self.assertEqual(sent_count, 1)
        send_telegram_message.assert_called_once()
        self.assertEqual(send_telegram_message.call_args.kwargs["chat_id"], int(expected.user.username))

    @patch("apps.vpn.services.notify_vpn_expiry_service.send_telegram_message")
    def test_sends_hour_notification_only_in_exact_one_hour_five_minute_window(
        self,
        send_telegram_message,
    ) -> None:
        now = timezone.now()
        starts_at = now + timedelta(hours=1)
        expected = VPNSubscriptionFactory(user__username="1004", expired_at=starts_at)
        VPNSubscriptionFactory(
            user__username="1005",
            expired_at=starts_at - timedelta(microseconds=1),
        )
        VPNSubscriptionFactory(
            user__username="1006",
            expired_at=starts_at + timedelta(minutes=5),
        )

        with patch("apps.vpn.services.notify_vpn_expiry_service.timezone.now", return_value=now):
            sent_count = get_notify_vpn_expiry_service()(window="hour")

        self.assertEqual(sent_count, 1)
        send_telegram_message.assert_called_once()
        self.assertEqual(send_telegram_message.call_args.kwargs["chat_id"], int(expected.user.username))

    @patch("apps.vpn.services.notify_vpn_expiry_service.send_telegram_message")
    def test_sends_expired_notification_only_in_prior_expiry_cycle_window(
        self,
        send_telegram_message,
    ) -> None:
        now = timezone.now()
        expected = VPNSubscriptionFactory(
            user__username="1007",
            is_active=False,
            expired_at=now - timedelta(minutes=7),
        )
        VPNSubscriptionFactory(
            user__username="1008",
            is_active=False,
            expired_at=now - timedelta(minutes=7, microseconds=1),
        )
        VPNSubscriptionFactory(
            user__username="1009",
            is_active=False,
            expired_at=now - timedelta(minutes=2),
        )

        with patch("apps.vpn.services.notify_vpn_expiry_service.timezone.now", return_value=now):
            sent_count = get_notify_vpn_expiry_service()(window="expired")

        self.assertEqual(sent_count, 1)
        send_telegram_message.assert_called_once()
        self.assertEqual(send_telegram_message.call_args.kwargs["chat_id"], int(expected.user.username))

    def test_vpn_templates_use_vpn_callback_and_duration_wording_without_changing_mtproto_templates(
        self,
    ) -> None:
        day_template = NotificationTemplate.objects.get(slug="vpn_before_expiry_1day")
        hour_template = NotificationTemplate.objects.get(slug="vpn_before_expiry_1hour")
        deactivated_template = NotificationTemplate.objects.get(slug="vpn_deactivated")
        for template in (day_template, hour_template, deactivated_template):
            rendered = template.render()
            self.assertEqual(rendered.markup.keyboard[0][0].callback_data, "vpn")

        self.assertIn("примерно через 24 часа", day_template.text)
        self.assertIn("примерно через 1 час", hour_template.text)
        mtproto_template = NotificationTemplate.objects.get(slug="before_expiry_1day")
        self.assertNotEqual(mtproto_template.button_callback_data, "vpn")
