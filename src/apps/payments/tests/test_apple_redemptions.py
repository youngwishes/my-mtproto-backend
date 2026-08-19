from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from unittest import mock

from django.db import OperationalError, close_old_connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.payments.enums import AppleRedemptionModeEnum
from apps.payments.exceptions import (
    AppleKeyRequired,
    AppleRedemptionRetryable,
    InsufficientApples,
    InvalidAppleRedemption,
    StaleAppleRedemption,
)
from apps.payments.models import AppleRedemption
from apps.payments.services import (
    ConfirmAppleRedemptionService,
    PreviewAppleRedemptionService,
    get_apple_status_service,
)
from apps.payments.services.dtos import (
    AppleRedemptionConfirmIn,
    AppleRedemptionConfirmOut,
    AppleRedemptionPreviewIn,
    AppleRedemptionPreviewOut,
    AppleStatusIn,
    AppleStatusOut,
)
from apps.payments.tests.factories import AppleCashbackPurchaseFactory
from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory


class TestGetAppleStatusService(TestCase):
    def test_status_reports_balance_level_progress_and_redeemability(self) -> None:
        user = SystemUserFactory(username="status-user", apple_balance=37)
        MTPRotoKeyFactory(
            user=user,
            expired_date=timezone.now() + timedelta(days=10),
        )

        result = get_apple_status_service()(
            request=AppleStatusIn(username=user.username),
        )

        self.assertEqual(
            result,
            AppleStatusOut(
                balance=37,
                eligible_purchase_count=0,
                level="Новичок",
                rate_percent=5,
                next_level_purchase_count=4,
                purchases_to_next_level=4,
                is_max_level=False,
                redeemable_days=2,
                missing_apples=0,
                has_existing_key=True,
            ),
        )

    def test_max_level_status_has_no_next_target_and_reports_missing_apples(self) -> None:
        user = SystemUserFactory(username="status-max", apple_balance=7)
        for index in range(7):
            AppleCashbackPurchaseFactory(
                payment__user=user,
                identity_key=f"stars:status-max-{index}:subscription",
                eligible_purchase_count_after=index + 1,
            )

        result = get_apple_status_service()(
            request=AppleStatusIn(username=user.username),
        )

        self.assertEqual(
            result,
            AppleStatusOut(
                balance=7,
                eligible_purchase_count=7,
                level="Мастер сада",
                rate_percent=15,
                next_level_purchase_count=None,
                purchases_to_next_level=None,
                is_max_level=True,
                redeemable_days=0,
                missing_apples=8,
                has_existing_key=False,
            ),
        )

    def test_storage_failure_returns_retryable_error(self) -> None:
        user = SystemUserFactory(username="status-storage")

        with mock.patch(
            "apps.payments.services.apple_redemptions.count_apple_cashback_purchases",
            side_effect=OperationalError("storage unavailable"),
        ), self.assertRaises(AppleRedemptionRetryable) as raised:
            get_apple_status_service()(
                request=AppleStatusIn(username=user.username),
            )

        self.assertEqual(raised.exception.telegram_id, user.username)


class TestPreviewAppleRedemptionService(TestCase):
    def test_one_day_preview_saves_quote_without_mutating_balance_or_key(self) -> None:
        now = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        user = SystemUserFactory(username="preview-one", apple_balance=37)
        key = MTPRotoKeyFactory(
            user=user,
            expired_date=now + timedelta(days=10),
        )
        original_expiry = key.expired_date
        service = PreviewAppleRedemptionService(clock=lambda: now)

        result = service(
            request=AppleRedemptionPreviewIn(
                username=user.username,
                mode=AppleRedemptionModeEnum.ONE_DAY,
            )
        )

        redemption = AppleRedemption.objects.get()
        self.assertEqual(
            result,
            AppleRedemptionPreviewOut(
                confirmation_id=redemption.pk,
                mode="one_day",
                apples_spent=15,
                days=1,
                projected_expired_date="30.08.26",
            ),
        )
        self.assertEqual(redemption.user, user)
        self.assertEqual(redemption.key, key)
        self.assertEqual(redemption.apples_spent, 15)
        self.assertEqual(redemption.quoted_expired_at, now + timedelta(days=11))
        self.assertIsNone(redemption.new_expired_at)
        self.assertIsNone(redemption.balance_after)
        user.refresh_from_db()
        key.refresh_from_db()
        self.assertEqual(user.apple_balance, 37)
        self.assertEqual(key.expired_date, original_expiry)

    def test_insufficient_balance_reports_missing_apples_without_mutation(self) -> None:
        now = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        user = SystemUserFactory(username="preview-low", apple_balance=14)
        key = MTPRotoKeyFactory(
            user=user,
            expired_date=now + timedelta(days=10),
        )
        original_expiry = key.expired_date

        with self.assertRaises(InsufficientApples) as raised:
            PreviewAppleRedemptionService(clock=lambda: now)(
                request=AppleRedemptionPreviewIn(
                    username=user.username,
                    mode=AppleRedemptionModeEnum.ONE_DAY,
                )
            )

        self.assertEqual(raised.exception.telegram_id, user.username)
        self.assertEqual(raised.exception.context, {"missing_apples": 1})
        self.assertFalse(AppleRedemption.objects.exists())
        user.refresh_from_db()
        key.refresh_from_db()
        self.assertEqual(user.apple_balance, 14)
        self.assertEqual(key.expired_date, original_expiry)

    def test_existing_key_is_required_without_creating_a_quote(self) -> None:
        user = SystemUserFactory(username="preview-no-key", apple_balance=15)

        with self.assertRaises(AppleKeyRequired) as raised:
            PreviewAppleRedemptionService(clock=timezone.now)(
                request=AppleRedemptionPreviewIn(
                    username=user.username,
                    mode=AppleRedemptionModeEnum.ONE_DAY,
                )
            )

        self.assertEqual(raised.exception.telegram_id, user.username)
        self.assertFalse(AppleRedemption.objects.exists())
        user.refresh_from_db()
        self.assertEqual(user.apple_balance, 15)

    def test_invalid_mode_is_rejected_without_creating_a_quote(self) -> None:
        user = SystemUserFactory(username="preview-invalid", apple_balance=15)
        MTPRotoKeyFactory(
            user=user,
            expired_date=timezone.now() + timedelta(days=1),
        )

        with self.assertRaises(InvalidAppleRedemption):
            PreviewAppleRedemptionService(clock=timezone.now)(
                request=AppleRedemptionPreviewIn(
                    username=user.username,
                    mode="custom_days",
                )
            )

        self.assertFalse(AppleRedemption.objects.exists())
        user.refresh_from_db()
        self.assertEqual(user.apple_balance, 15)

    def test_redeem_all_quotes_only_complete_packs_and_preserves_balance(self) -> None:
        now = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        user = SystemUserFactory(username="preview-all", apple_balance=37)
        key = MTPRotoKeyFactory(
            user=user,
            expired_date=now + timedelta(days=5),
        )

        result = PreviewAppleRedemptionService(clock=lambda: now)(
            request=AppleRedemptionPreviewIn(
                username=user.username,
                mode=AppleRedemptionModeEnum.ALL,
            )
        )

        self.assertEqual(result.apples_spent, 30)
        self.assertEqual(result.days, 2)
        self.assertEqual(result.projected_expired_date, "26.08.26")
        redemption = AppleRedemption.objects.get(pk=result.confirmation_id)
        self.assertEqual(redemption.apples_spent, 30)
        self.assertEqual(redemption.quoted_expired_at, now + timedelta(days=7))
        user.refresh_from_db()
        key.refresh_from_db()
        self.assertEqual(user.apple_balance, 37)
        self.assertEqual(key.expired_date, now + timedelta(days=5))

    def test_expired_cleaned_key_quotes_from_preview_time(self) -> None:
        now = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        user = SystemUserFactory(username="preview-expired", apple_balance=15)
        key = MTPRotoKeyFactory(
            user=user,
            expired_date=now - timedelta(days=7),
            is_active=False,
            was_deleted=True,
        )

        result = PreviewAppleRedemptionService(clock=lambda: now)(
            request=AppleRedemptionPreviewIn(
                username=user.username,
                mode=AppleRedemptionModeEnum.ONE_DAY,
            )
        )

        self.assertEqual(result.projected_expired_date, "20.08.26")
        self.assertEqual(AppleRedemption.objects.get().key, key)

    def test_preview_prefers_latest_valid_active_key_over_cleaned_fallback(self) -> None:
        now = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        user = SystemUserFactory(username="preview-selection", apple_balance=15)
        MTPRotoKeyFactory(
            user=user,
            expired_date=now + timedelta(days=3),
        )
        selected = MTPRotoKeyFactory(
            user=user,
            expired_date=now + timedelta(days=5),
        )
        MTPRotoKeyFactory(
            user=user,
            expired_date=now + timedelta(days=30),
            is_active=False,
            was_deleted=True,
        )

        preview = PreviewAppleRedemptionService(clock=lambda: now)(
            request=AppleRedemptionPreviewIn(
                username=user.username,
                mode=AppleRedemptionModeEnum.ONE_DAY,
            )
        )

        self.assertEqual(
            AppleRedemption.objects.get(pk=preview.confirmation_id).key,
            selected,
        )

    def test_storage_failure_returns_retryable_without_mutation(self) -> None:
        now = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        user = SystemUserFactory(username="preview-storage", apple_balance=15)
        key = MTPRotoKeyFactory(
            user=user,
            expired_date=now + timedelta(days=1),
        )
        original_expiry = key.expired_date

        with mock.patch(
            "apps.payments.services.apple_redemptions.create_apple_redemption",
            side_effect=OperationalError("storage unavailable"),
        ), self.assertRaises(AppleRedemptionRetryable):
            PreviewAppleRedemptionService(clock=lambda: now)(
                request=AppleRedemptionPreviewIn(
                    username=user.username,
                    mode=AppleRedemptionModeEnum.ONE_DAY,
                )
            )

        self.assertFalse(AppleRedemption.objects.exists())
        user.refresh_from_db()
        key.refresh_from_db()
        self.assertEqual(user.apple_balance, 15)
        self.assertEqual(key.expired_date, original_expiry)


class TestConfirmAppleRedemptionService(TestCase):
    def test_active_key_confirmation_debits_quote_and_extends_current_expiry(self) -> None:
        preview_at = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        confirm_at = preview_at + timedelta(hours=2)
        user = SystemUserFactory(username="confirm-active", apple_balance=37)
        key = MTPRotoKeyFactory(
            user=user,
            expired_date=preview_at + timedelta(days=10),
        )
        original_expiry = key.expired_date
        preview = PreviewAppleRedemptionService(clock=lambda: preview_at)(
            request=AppleRedemptionPreviewIn(
                username=user.username,
                mode=AppleRedemptionModeEnum.ONE_DAY,
            )
        )
        enqueue_push = mock.Mock()
        service = ConfirmAppleRedemptionService(
            clock=lambda: confirm_at,
            enqueue_push=enqueue_push,
        )

        with self.captureOnCommitCallbacks(execute=True):
            result = service(
                request=AppleRedemptionConfirmIn(
                    username=user.username,
                    confirmation_id=preview.confirmation_id,
                )
            )

        self.assertEqual(
            result,
            AppleRedemptionConfirmOut(
                apples_spent=15,
                days=1,
                expired_date="30.08.26",
                balance=22,
            ),
        )
        user.refresh_from_db()
        key.refresh_from_db()
        redemption = AppleRedemption.objects.get(pk=preview.confirmation_id)
        self.assertEqual(user.apple_balance, 22)
        self.assertEqual(key.expired_date, original_expiry + timedelta(days=1))
        self.assertEqual(redemption.new_expired_at, key.expired_date)
        self.assertEqual(redemption.balance_after, 22)
        enqueue_push.assert_not_called()

    def test_confirmation_resets_reminder_once_and_repeat_preserves_later_true(
        self,
    ) -> None:
        now = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        user = SystemUserFactory(username="confirm-reminder", apple_balance=15)
        key = MTPRotoKeyFactory(
            user=user,
            expired_date=now - timedelta(days=7),
            is_active=False,
            was_deleted=True,
            user_notified=True,
        )
        preview = PreviewAppleRedemptionService(clock=lambda: now)(
            request=AppleRedemptionPreviewIn(
                username=user.username,
                mode=AppleRedemptionModeEnum.ONE_DAY,
            )
        )
        enqueue_push = mock.Mock()
        service = ConfirmAppleRedemptionService(
            clock=lambda: now,
            enqueue_push=enqueue_push,
        )
        request = AppleRedemptionConfirmIn(
            username=user.username,
            confirmation_id=preview.confirmation_id,
        )

        with self.captureOnCommitCallbacks(execute=True):
            first = service(request=request)

        key.refresh_from_db()
        user.refresh_from_db()
        first_expiry = key.expired_date
        first_balance = user.apple_balance
        self.assertEqual(first_expiry, now + timedelta(days=1))
        self.assertFalse(key.user_notified)

        key.user_notified = True
        key.save(update_fields=["user_notified"])

        second = service(request=request)

        key.refresh_from_db()
        user.refresh_from_db()
        self.assertEqual(second, first)
        self.assertEqual(key.expired_date, first_expiry)
        self.assertEqual(user.apple_balance, first_balance)
        self.assertTrue(key.user_notified)
        enqueue_push.assert_called_once_with(key_id=key.pk)

    def test_reduced_balance_makes_quote_stale_without_mutation(self) -> None:
        now = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        user = SystemUserFactory(username="confirm-stale-balance", apple_balance=37)
        key = MTPRotoKeyFactory(
            user=user,
            expired_date=now + timedelta(days=10),
        )
        original_expiry = key.expired_date
        preview = PreviewAppleRedemptionService(clock=lambda: now)(
            request=AppleRedemptionPreviewIn(
                username=user.username,
                mode=AppleRedemptionModeEnum.ALL,
            )
        )
        user.apple_balance = 29
        user.save(update_fields=["apple_balance"])

        with self.assertRaises(StaleAppleRedemption):
            ConfirmAppleRedemptionService(
                clock=lambda: now,
                enqueue_push=mock.Mock(),
            )(
                request=AppleRedemptionConfirmIn(
                    username=user.username,
                    confirmation_id=preview.confirmation_id,
                )
            )

        user.refresh_from_db()
        key.refresh_from_db()
        redemption = AppleRedemption.objects.get(pk=preview.confirmation_id)
        self.assertEqual(user.apple_balance, 29)
        self.assertEqual(key.expired_date, original_expiry)
        self.assertIsNone(redemption.new_expired_at)
        self.assertIsNone(redemption.balance_after)

    def test_storage_failure_rolls_back_balance_and_expiry(self) -> None:
        now = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        user = SystemUserFactory(username="confirm-storage", apple_balance=15)
        key = MTPRotoKeyFactory(
            user=user,
            expired_date=now + timedelta(days=10),
        )
        original_expiry = key.expired_date
        preview = PreviewAppleRedemptionService(clock=lambda: now)(
            request=AppleRedemptionPreviewIn(
                username=user.username,
                mode=AppleRedemptionModeEnum.ONE_DAY,
            )
        )

        with mock.patch(
            "apps.payments.models.AppleRedemption.save",
            side_effect=OperationalError("storage unavailable"),
        ), self.assertRaises(AppleRedemptionRetryable) as raised:
            ConfirmAppleRedemptionService(
                clock=lambda: now,
                enqueue_push=mock.Mock(),
            )(
                request=AppleRedemptionConfirmIn(
                    username=user.username,
                    confirmation_id=preview.confirmation_id,
                )
            )

        self.assertEqual(raised.exception.telegram_id, user.username)
        user.refresh_from_db()
        key.refresh_from_db()
        redemption = AppleRedemption.objects.get(pk=preview.confirmation_id)
        self.assertEqual(user.apple_balance, 15)
        self.assertEqual(key.expired_date, original_expiry)
        self.assertIsNone(redemption.new_expired_at)
        self.assertIsNone(redemption.balance_after)

    def test_expired_key_reactivates_from_confirmation_and_pushes_after_commit(self) -> None:
        preview_at = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        confirmation_at = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
        user = SystemUserFactory(username="confirm-expired", apple_balance=15)
        key = MTPRotoKeyFactory(
            user=user,
            expired_date=preview_at - timedelta(days=7),
            is_active=False,
            was_deleted=True,
        )
        preview = PreviewAppleRedemptionService(clock=lambda: preview_at)(
            request=AppleRedemptionPreviewIn(
                username=user.username,
                mode=AppleRedemptionModeEnum.ONE_DAY,
            )
        )
        enqueue_push = mock.Mock()

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            result = ConfirmAppleRedemptionService(
                clock=lambda: confirmation_at,
                enqueue_push=enqueue_push,
            )(
                request=AppleRedemptionConfirmIn(
                    username=user.username,
                    confirmation_id=preview.confirmation_id,
                )
            )
            enqueue_push.assert_not_called()

        self.assertEqual(result.expired_date, "22.08.26")
        self.assertEqual(result.balance, 0)
        key.refresh_from_db()
        self.assertEqual(key.expired_date, confirmation_at + timedelta(days=1))
        self.assertTrue(key.is_active)
        self.assertFalse(key.was_deleted)
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        enqueue_push.assert_called_once_with(key_id=key.pk)

    def test_new_credit_after_preview_does_not_enlarge_redeem_all_quote(self) -> None:
        now = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        user = SystemUserFactory(username="confirm-immutable", apple_balance=37)
        key = MTPRotoKeyFactory(
            user=user,
            expired_date=now + timedelta(days=5),
        )
        original_expiry = key.expired_date
        preview = PreviewAppleRedemptionService(clock=lambda: now)(
            request=AppleRedemptionPreviewIn(
                username=user.username,
                mode=AppleRedemptionModeEnum.ALL,
            )
        )
        user.apple_balance = 52
        user.save(update_fields=["apple_balance"])

        result = ConfirmAppleRedemptionService(
            clock=lambda: now,
            enqueue_push=mock.Mock(),
        )(
            request=AppleRedemptionConfirmIn(
                username=user.username,
                confirmation_id=preview.confirmation_id,
            )
        )

        self.assertEqual(result.apples_spent, 30)
        self.assertEqual(result.days, 2)
        self.assertEqual(result.balance, 22)
        key.refresh_from_db()
        self.assertEqual(key.expired_date, original_expiry + timedelta(days=2))

    def test_same_quoted_key_uses_its_current_expiry_at_confirmation(self) -> None:
        now = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        user = SystemUserFactory(username="confirm-shifted", apple_balance=15)
        key = MTPRotoKeyFactory(
            user=user,
            expired_date=now + timedelta(days=5),
        )
        preview = PreviewAppleRedemptionService(clock=lambda: now)(
            request=AppleRedemptionPreviewIn(
                username=user.username,
                mode=AppleRedemptionModeEnum.ONE_DAY,
            )
        )
        key.expired_date = now + timedelta(days=8)
        key.save(update_fields=["expired_date"])

        result = ConfirmAppleRedemptionService(
            clock=lambda: now,
            enqueue_push=mock.Mock(),
        )(
            request=AppleRedemptionConfirmIn(
                username=user.username,
                confirmation_id=preview.confirmation_id,
            )
        )

        self.assertEqual(result.expired_date, "28.08.26")
        key.refresh_from_db()
        self.assertEqual(key.expired_date, now + timedelta(days=9))

    def test_repeated_confirmation_returns_saved_outcome_without_second_effect(self) -> None:
        now = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        user = SystemUserFactory(username="confirm-repeat", apple_balance=37)
        key = MTPRotoKeyFactory(
            user=user,
            expired_date=now + timedelta(days=5),
        )
        preview = PreviewAppleRedemptionService(clock=lambda: now)(
            request=AppleRedemptionPreviewIn(
                username=user.username,
                mode=AppleRedemptionModeEnum.ONE_DAY,
            )
        )
        service = ConfirmAppleRedemptionService(
            clock=lambda: now,
            enqueue_push=mock.Mock(),
        )
        request = AppleRedemptionConfirmIn(
            username=user.username,
            confirmation_id=preview.confirmation_id,
        )

        first = service(request=request)
        first_expiry = key.expired_date + timedelta(days=1)
        user.apple_balance = 99
        user.save(update_fields=["apple_balance"])
        key.delete()
        second = service(request=request)

        self.assertEqual(second, first)
        self.assertEqual(second.balance, 22)
        self.assertEqual(
            second.expired_date,
            first_expiry.date().strftime("%d.%m.%y"),
        )
        user.refresh_from_db()
        self.assertEqual(user.apple_balance, 99)
        self.assertEqual(AppleRedemption.objects.get().new_expired_at, first_expiry)

    def test_other_owner_cannot_confirm_or_observe_saved_outcome(self) -> None:
        now = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        owner = SystemUserFactory(username="confirm-owner", apple_balance=15)
        other = SystemUserFactory(username="confirm-other", apple_balance=15)
        key = MTPRotoKeyFactory(
            user=owner,
            expired_date=now + timedelta(days=5),
        )
        original_expiry = key.expired_date
        preview = PreviewAppleRedemptionService(clock=lambda: now)(
            request=AppleRedemptionPreviewIn(
                username=owner.username,
                mode=AppleRedemptionModeEnum.ONE_DAY,
            )
        )

        with self.assertRaises(InvalidAppleRedemption):
            ConfirmAppleRedemptionService(
                clock=lambda: now,
                enqueue_push=mock.Mock(),
            )(
                request=AppleRedemptionConfirmIn(
                    username=other.username,
                    confirmation_id=preview.confirmation_id,
                )
            )

        owner.refresh_from_db()
        other.refresh_from_db()
        key.refresh_from_db()
        self.assertEqual(owner.apple_balance, 15)
        self.assertEqual(other.apple_balance, 15)
        self.assertEqual(key.expired_date, original_expiry)

    def test_replaced_quoted_key_is_stale_without_mutation(self) -> None:
        now = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        user = SystemUserFactory(username="confirm-replaced", apple_balance=15)
        quoted_key = MTPRotoKeyFactory(
            user=user,
            expired_date=now + timedelta(days=5),
        )
        preview = PreviewAppleRedemptionService(clock=lambda: now)(
            request=AppleRedemptionPreviewIn(
                username=user.username,
                mode=AppleRedemptionModeEnum.ONE_DAY,
            )
        )
        replacement = MTPRotoKeyFactory(
            user=user,
            expired_date=now + timedelta(days=10),
        )

        with self.assertRaises(StaleAppleRedemption):
            ConfirmAppleRedemptionService(
                clock=lambda: now,
                enqueue_push=mock.Mock(),
            )(
                request=AppleRedemptionConfirmIn(
                    username=user.username,
                    confirmation_id=preview.confirmation_id,
                )
            )

        user.refresh_from_db()
        quoted_key.refresh_from_db()
        replacement.refresh_from_db()
        self.assertEqual(user.apple_balance, 15)
        self.assertEqual(quoted_key.expired_date, now + timedelta(days=5))
        self.assertEqual(replacement.expired_date, now + timedelta(days=10))
        self.assertIsNone(AppleRedemption.objects.get().new_expired_at)

    def test_deleted_quoted_key_is_stale_without_debit(self) -> None:
        now = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        user = SystemUserFactory(username="confirm-deleted", apple_balance=15)
        key = MTPRotoKeyFactory(
            user=user,
            expired_date=now + timedelta(days=5),
        )
        preview = PreviewAppleRedemptionService(clock=lambda: now)(
            request=AppleRedemptionPreviewIn(
                username=user.username,
                mode=AppleRedemptionModeEnum.ONE_DAY,
            )
        )
        key.delete()

        with self.assertRaises(StaleAppleRedemption):
            ConfirmAppleRedemptionService(
                clock=lambda: now,
                enqueue_push=mock.Mock(),
            )(
                request=AppleRedemptionConfirmIn(
                    username=user.username,
                    confirmation_id=preview.confirmation_id,
                )
            )

        user.refresh_from_db()
        redemption = AppleRedemption.objects.get(pk=preview.confirmation_id)
        self.assertEqual(user.apple_balance, 15)
        self.assertIsNone(redemption.key_id)
        self.assertIsNone(redemption.new_expired_at)


class TestConcurrentAppleRedemptionConfirmation(TransactionTestCase):
    def test_concurrent_confirmation_has_one_debit_and_extension(self) -> None:
        now = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        user = SystemUserFactory(username="confirm-concurrent", apple_balance=15)
        key = MTPRotoKeyFactory(
            user=user,
            expired_date=now + timedelta(days=5),
        )
        original_expiry = key.expired_date
        preview = PreviewAppleRedemptionService(clock=lambda: now)(
            request=AppleRedemptionPreviewIn(
                username=user.username,
                mode=AppleRedemptionModeEnum.ONE_DAY,
            )
        )
        request = AppleRedemptionConfirmIn(
            username=user.username,
            confirmation_id=preview.confirmation_id,
        )
        barrier = Barrier(2)

        def confirm() -> AppleRedemptionConfirmOut | AppleRedemptionRetryable:
            close_old_connections()
            barrier.wait()
            try:
                return ConfirmAppleRedemptionService(
                    clock=lambda: now,
                    enqueue_push=lambda **_: None,
                )(request=request)
            except AppleRedemptionRetryable as exc:
                return exc
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: confirm(), range(2)))

        winner = ConfirmAppleRedemptionService(
            clock=lambda: now,
            enqueue_push=lambda **_: None,
        )(request=request)
        for outcome in outcomes:
            if isinstance(outcome, AppleRedemptionConfirmOut):
                self.assertEqual(outcome, winner)

        user.refresh_from_db()
        key.refresh_from_db()
        self.assertEqual(user.apple_balance, 0)
        self.assertEqual(key.expired_date, original_expiry + timedelta(days=1))
        self.assertEqual(winner.apples_spent, 15)
        self.assertEqual(winner.balance, 0)
