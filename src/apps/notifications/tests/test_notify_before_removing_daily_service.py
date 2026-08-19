from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.notifications.services import get_notify_before_removing_daily_service
from apps.payments.enums import AppleRedemptionModeEnum
from apps.payments.services import (
    ConfirmAppleRedemptionService,
    PreviewAppleRedemptionService,
    get_extend_key_service,
)
from apps.payments.services.dtos import (
    AppleRedemptionConfirmIn,
    AppleRedemptionPreviewIn,
)
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
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_conditional_mark_succeeds_when_expiry_is_unchanged(
        self,
        mock_send,
        mock_get_template,
        _time,
    ) -> None:
        now = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        selected_expiry = now + timedelta(days=1)
        self.key.expired_date = selected_expiry
        self.key.user_notified = False
        self.key.save(update_fields=["expired_date", "user_notified"])

        with mock.patch(f"{_SERVICE_MODULE}.timezone.now", return_value=now):
            get_notify_before_removing_daily_service()()

        self.key.refresh_from_db()
        mock_send.assert_called_once()
        self.assertEqual(self.key.expired_date, selected_expiry)
        self.assertTrue(self.key.user_notified)

    @mock.patch(f"{_SERVICE_MODULE}.time")
    @mock.patch(f"{_SERVICE_MODULE}.get_template")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_stale_mark_is_noop_after_paid_extension_during_send(
        self,
        mock_send,
        mock_get_template,
        _time,
    ) -> None:
        now = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        selected_expiry = now + timedelta(days=1)
        self.key.expired_date = selected_expiry
        self.key.user_notified = False
        self.key.save(update_fields=["expired_date", "user_notified"])
        mock_send.side_effect = lambda **_kwargs: get_extend_key_service()(
            key=self.key,
            reset_user_notified=True,
        )

        with mock.patch(f"{_SERVICE_MODULE}.timezone.now", return_value=now):
            get_notify_before_removing_daily_service()()

        expected_expiry = selected_expiry + timedelta(days=30)
        self.key.refresh_from_db()
        mock_send.assert_called_once()
        self.assertEqual(self.key.expired_date, expected_expiry)
        self.assertFalse(self.key.user_notified)

    @mock.patch(f"{_SERVICE_MODULE}.time")
    @mock.patch(f"{_SERVICE_MODULE}.get_template")
    @mock.patch(f"{_SERVICE_MODULE}.send_telegram_message")
    def test_stale_mark_is_noop_after_apple_redemption_during_send(
        self,
        mock_send,
        mock_get_template,
        _time,
    ) -> None:
        now = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        selected_expiry = now + timedelta(days=1)
        self.user.apple_balance = 15
        self.user.save(update_fields=["apple_balance"])
        self.key.expired_date = selected_expiry
        self.key.user_notified = False
        self.key.save(update_fields=["expired_date", "user_notified"])
        preview = PreviewAppleRedemptionService(clock=lambda: now)(
            request=AppleRedemptionPreviewIn(
                username=self.user.username,
                mode=AppleRedemptionModeEnum.ONE_DAY,
            )
        )
        confirm = ConfirmAppleRedemptionService(
            clock=lambda: now,
            enqueue_push=mock.Mock(),
        )
        mock_send.side_effect = lambda **_kwargs: confirm(
            request=AppleRedemptionConfirmIn(
                username=self.user.username,
                confirmation_id=preview.confirmation_id,
            )
        )

        with mock.patch(f"{_SERVICE_MODULE}.timezone.now", return_value=now):
            get_notify_before_removing_daily_service()()

        expected_expiry = selected_expiry + timedelta(days=1)
        self.key.refresh_from_db()
        self.user.refresh_from_db()
        mock_send.assert_called_once()
        self.assertEqual(self.key.expired_date, expected_expiry)
        self.assertEqual(self.user.apple_balance, 0)
        self.assertFalse(self.key.user_notified)

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
