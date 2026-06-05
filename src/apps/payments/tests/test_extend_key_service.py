from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from apps.payments.models import Payment
from apps.payments.services.extend_key_service import get_extend_key_service
from apps.payments.tests.factories import PaymentFactory
from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestExtendKeyService(TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory()
        self.vds = VDSInstanceFactory()
        self.service = get_extend_key_service()

    def test_extends_key_by_subscription_period(self) -> None:
        key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
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

    def test_detaches_old_payments_from_key(self) -> None:
        key = MTPRotoKeyFactory(
            user=self.user,
            vds=self.vds,
            expired_date=timezone.now() + timedelta(days=10),
            was_deleted=False,
        )
        old_payment = PaymentFactory(user=self.user, key=key)

        self.service(key=key)

        old_payment.refresh_from_db()
        self.assertIsNone(old_payment.key)
