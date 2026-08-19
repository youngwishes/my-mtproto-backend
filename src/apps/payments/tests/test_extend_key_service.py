from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from apps.payments.models import Payment
from apps.payments.services.extend_key_service import get_extend_key_service
from apps.payments.tests.factories import PaymentFactory
from apps.users.tests.factories import SystemUserFactory
from apps.vds.selectors import get_unnotified_keys_expiring_on_date
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestExtendKeyService(TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory()
        self.vds = VDSInstanceFactory()
        self.service = get_extend_key_service()

    def test_extends_key_by_subscription_period(self) -> None:
        key = MTPRotoKeyFactory(
            user=self.user,
            expired_date=timezone.now() + timedelta(days=10),
            was_deleted=False,
        )
        original_expired = key.expired_date

        self.service(key=key)

        key.refresh_from_db()
        self.assertAlmostEqual(
            key.expired_date,
            original_expired + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS),
            delta=timedelta(seconds=5),
        )

    def test_paid_extension_resets_one_day_reminder(self) -> None:
        key = MTPRotoKeyFactory(
            user=self.user,
            expired_date=timezone.now() + timedelta(days=10),
            user_notified=True,
            was_deleted=False,
        )
        original_expired = key.expired_date

        self.service(key=key, reset_user_notified=True)

        key.refresh_from_db()
        self.assertAlmostEqual(
            key.expired_date,
            original_expired + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS),
            delta=timedelta(seconds=5),
        )
        self.assertFalse(key.user_notified)
        self.assertIn(
            key,
            get_unnotified_keys_expiring_on_date(date=key.expired_date.date()),
        )

    def test_default_extension_preserves_one_day_reminder(self) -> None:
        key = MTPRotoKeyFactory(
            user=self.user,
            expired_date=timezone.now() + timedelta(days=10),
            user_notified=True,
            was_deleted=False,
        )

        self.service(key=key)

        key.refresh_from_db()
        self.assertTrue(key.user_notified)
        self.assertNotIn(
            key,
            get_unnotified_keys_expiring_on_date(date=key.expired_date.date()),
        )

    def test_default_extension_does_not_overwrite_newer_reminder(self) -> None:
        key = MTPRotoKeyFactory(
            user=self.user,
            expired_date=timezone.now() + timedelta(days=10),
            user_notified=False,
            was_deleted=False,
        )
        original_expired = key.expired_date
        key.__class__.objects.filter(pk=key.pk).update(user_notified=True)

        self.service(key=key)

        key.refresh_from_db()
        self.assertAlmostEqual(
            key.expired_date,
            original_expired + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS),
            delta=timedelta(seconds=5),
        )
        self.assertTrue(key.user_notified)

    def test_detaches_old_payments_from_key(self) -> None:
        key = MTPRotoKeyFactory(
            user=self.user,
            expired_date=timezone.now() + timedelta(days=10),
            was_deleted=False,
        )
        old_payment = PaymentFactory(user=self.user, key=key)

        self.service(key=key)

        old_payment.refresh_from_db()
        self.assertIsNone(old_payment.key)
