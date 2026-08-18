from __future__ import annotations

from datetime import timedelta

from django.db import IntegrityError, models, transaction
from django.test import TestCase
from django.utils import timezone

from apps.payments import AppleCashbackPurchase, AppleRedemption
from apps.payments.tests.factories import PaymentFactory
from apps.users.models import SystemUser
from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory


class TestAppleCashbackPurchaseModel(TestCase):
    def test_purchase_ledger_has_only_the_approved_fields(self) -> None:
        self.assertEqual(
            {field.name for field in AppleCashbackPurchase._meta.fields},
            {
                "id",
                "is_active",
                "created_at",
                "updated_at",
                "payment",
                "identity_key",
                "rate_percent",
                "apples_earned",
                "balance_after",
                "eligible_purchase_count_after",
                "result_expired_at",
            },
        )

    def test_purchase_identity_is_unique_and_payment_is_cascaded(self) -> None:
        payment_field = AppleCashbackPurchase._meta.get_field("payment")
        self.assertIsInstance(payment_field, models.OneToOneField)
        self.assertIs(payment_field.remote_field.on_delete, models.CASCADE)

        AppleCashbackPurchase.objects.create(
            payment=PaymentFactory(),
            identity_key="stars:payment-1:subscription",
            rate_percent=5,
            apples_earned=5,
            balance_after=5,
            eligible_purchase_count_after=1,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AppleCashbackPurchase.objects.create(
                    payment=PaymentFactory(),
                    identity_key="stars:payment-1:subscription",
                    rate_percent=5,
                    apples_earned=5,
                    balance_after=5,
                    eligible_purchase_count_after=1,
                )

    def test_historical_purchase_snapshots_are_nullable(self) -> None:
        purchase = AppleCashbackPurchase.objects.create(
            payment=PaymentFactory(),
            identity_key="legacy:1",
            rate_percent=None,
            apples_earned=0,
            balance_after=0,
            eligible_purchase_count_after=1,
            result_expired_at=None,
        )

        self.assertIsNone(purchase.rate_percent)
        self.assertIsNone(purchase.result_expired_at)


class TestAppleRedemptionModel(TestCase):
    def test_redemption_ledger_has_only_the_approved_fields(self) -> None:
        self.assertEqual(
            {field.name for field in AppleRedemption._meta.fields},
            {
                "id",
                "is_active",
                "created_at",
                "updated_at",
                "user",
                "key",
                "apples_spent",
                "quoted_expired_at",
                "new_expired_at",
                "balance_after",
            },
        )

    def test_key_is_nullable_and_set_null_when_the_quoted_key_is_deleted(self) -> None:
        key_field = AppleRedemption._meta.get_field("key")
        self.assertTrue(key_field.null)
        self.assertIs(key_field.remote_field.on_delete, models.SET_NULL)

        user = SystemUserFactory()
        key = MTPRotoKeyFactory(user=user)
        redemption = AppleRedemption.objects.create(
            user=user,
            key=key,
            apples_spent=15,
            quoted_expired_at=timezone.now() + timedelta(days=1),
        )
        key.delete()

        redemption.refresh_from_db()
        self.assertIsNone(redemption.key)


class TestSystemUserAppleBalance(TestCase):
    def test_apple_balance_defaults_to_zero_and_database_rejects_negative_values(self) -> None:
        user = SystemUserFactory()

        self.assertEqual(user.apple_balance, 0)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SystemUser.objects.filter(pk=user.pk).update(apple_balance=-1)
