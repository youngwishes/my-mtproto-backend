from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

from django.db import OperationalError, close_old_connections
from django.test import TransactionTestCase
from django.utils import timezone

from apps.payments.enums import PaymentProviderEnum, ProductCodeEnum
from apps.payments.models import AppleCashbackPurchase, GiftCertificate, Payment
from apps.payments.services import (
    get_create_gift_certificate_service,
    get_create_payment_service,
)
from apps.payments.services.dtos import (
    CreateGiftCertificateIn,
    CreateGiftCertificateOut,
    CreatePaymentIn,
    CreatePaymentOut,
)
from apps.payments.tests.factories import ProductFactory
from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory


class TestAppleCashbackPurchaseConcurrency(TransactionTestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory(username="cashback-concurrent")
        ProductFactory(
            code=ProductCodeEnum.MTPROTO_30D,
            price=Decimal("9900"),
            currency="RUB",
        )

    def test_concurrent_subscription_identity_has_one_extension_and_credit(self) -> None:
        key = MTPRotoKeyFactory(
            user=self.user,
            expired_date=timezone.now() + timedelta(days=10),
        )
        original_expiry = key.expired_date
        request = CreatePaymentIn(
            username=self.user.username,
            charge_id="concurrent-subscription",
            provider=PaymentProviderEnum.STARS,
        )
        barrier = Barrier(2)

        def purchase() -> CreatePaymentOut | OperationalError:
            close_old_connections()
            barrier.wait()
            try:
                return get_create_payment_service()(payment=request)
            except OperationalError as exc:
                return exc
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: purchase(), range(2)))

        self.assertTrue(
            all(isinstance(outcome, (CreatePaymentOut, OperationalError)) for outcome in outcomes)
        )
        winner = get_create_payment_service()(payment=request)
        for outcome in outcomes:
            if isinstance(outcome, CreatePaymentOut):
                self.assertEqual(outcome, winner)
        key.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(key.expired_date, original_expiry + timedelta(days=30))
        self.assertEqual(self.user.apple_balance, 5)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(AppleCashbackPurchase.objects.count(), 1)
        self.assertEqual(winner.loyalty.balance, 5)

    def test_concurrent_gift_identity_has_one_certificate_and_credit(self) -> None:
        request = CreateGiftCertificateIn(
            username=self.user.username,
            charge_id="concurrent-gift",
            provider=PaymentProviderEnum.YUKASSA,
        )
        barrier = Barrier(2)

        def purchase() -> CreateGiftCertificateOut | OperationalError:
            close_old_connections()
            barrier.wait()
            try:
                return get_create_gift_certificate_service()(certificate=request)
            except OperationalError as exc:
                return exc
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: purchase(), range(2)))

        self.assertTrue(
            all(
                isinstance(outcome, (CreateGiftCertificateOut, OperationalError))
                for outcome in outcomes
            )
        )
        winner = get_create_gift_certificate_service()(certificate=request)
        for outcome in outcomes:
            if isinstance(outcome, CreateGiftCertificateOut):
                self.assertEqual(outcome, winner)
        self.user.refresh_from_db()
        self.assertEqual(self.user.apple_balance, 5)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(GiftCertificate.objects.count(), 1)
        self.assertEqual(AppleCashbackPurchase.objects.count(), 1)
        self.assertEqual(winner.code, GiftCertificate.objects.get().code)
