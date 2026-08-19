from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from threading import Event
from unittest import mock

from django.db import OperationalError, close_old_connections, connection, transaction
from django.test import SimpleTestCase, TestCase, TransactionTestCase

from apps.payments.enums import (
    CryptoPaymentIntentStatusEnum,
    PaymentKindEnum,
    PaymentProviderEnum,
    ProductCodeEnum,
)
from apps.payments.exceptions import CryptoPaymentRetryable
from apps.payments.models import AppleCashbackPurchase, GiftCertificate, Payment
from apps.payments.services import CreatePaymentService
from apps.payments.services.apply_crypto_payment import ApplyCryptoPaymentService
from apps.payments.services.extend_key_service import get_extend_key_service
from apps.payments.services.gift_certificates import get_create_gift_certificate_service
from apps.payments.tests.factories import (
    AppleCashbackPurchaseFactory,
    CryptoPaymentIntentFactory,
    GiftCertificateFactory,
    PaymentFactory,
    make_crypto_invoice,
)
from apps.users.tests.factories import SystemUserFactory
from apps.vds.exceptions import KeysLimitReached
from apps.vds.models import MTPRotoKey
from apps.vds.services import get_issue_key_on_commit_service
from apps.vpn.models import VPNSubscription
from apps.vpn.services.fulfill_vpn_purchase_service import FulfillVPNPurchaseService


class TestCryptoPaymentRetryable(SimpleTestCase):
    def test_exposes_safe_retry_context_for_the_initiator(self) -> None:
        error = CryptoPaymentRetryable("123456", reason_code="processing")

        self.assertEqual(error.telegram_id, "123456")
        self.assertEqual(error.context, {"reason_code": "processing"})


class ApplyCryptoPaymentServiceMixin:
    now = datetime(2026, 8, 2, 12, 25, tzinfo=UTC)

    def build_service(self) -> ApplyCryptoPaymentService:
        self.schedule_profiles = mock.Mock()
        self.enqueue_notification = mock.Mock()
        return ApplyCryptoPaymentService(
            create_payment_service=CreatePaymentService(
                extend_key_service=get_extend_key_service(),
                issue_key_service=get_issue_key_on_commit_service(),
            ),
            fulfill_vpn_purchase_service=FulfillVPNPurchaseService(
                schedule_profiles=self.schedule_profiles,
                subscription_base_url="https://vpn.example",
            ),
            create_gift_certificate_service=get_create_gift_certificate_service(),
            enqueue_notification=self.enqueue_notification,
            clock=lambda: self.now,
        )

    def make_payment(
        self,
        *,
        intent_id: int,
        invoice_id: int,
        paid: bool = True,
        provider_amount: Decimal = Decimal("1.00"),
    ):
        from apps.payments.services.dtos import ValidatedCryptoPaymentDTO

        return ValidatedCryptoPaymentDTO(
            intent_id=intent_id,
            invoice=make_crypto_invoice(
                invoice_id=invoice_id,
                amount=provider_amount,
                payload="provider-payer-data-must-not-select-owner",
                paid_at=self.now if paid else None,
            ),
        )


class TestApplyCryptoPaymentService(ApplyCryptoPaymentServiceMixin, TestCase):
    def setUp(self) -> None:
        self.initiator = SystemUserFactory(username="1487189460")
        self.service = self.build_service()

    @mock.patch("apps.vds.services.issue_key_service.push_key_to_servers_task.delay")
    def test_each_kind_fulfills_once_for_intent_initiator(
        self, push_key: mock.Mock
    ) -> None:
        cases = (
            (PaymentKindEnum.SUBSCRIPTION, ProductCodeEnum.MTPROTO_30D),
            (PaymentKindEnum.VPN_SUBSCRIPTION, ProductCodeEnum.VPN_30D),
            (PaymentKindEnum.GIFT_CERTIFICATE, ProductCodeEnum.MTPROTO_30D),
        )

        for offset, (kind, product_code) in enumerate(cases, start=1):
            with self.subTest(kind=kind):
                intent = CryptoPaymentIntentFactory(
                    initiator=self.initiator,
                    purchase_kind=kind,
                    product_code=product_code,
                    status=CryptoPaymentIntentStatusEnum.LOCAL_EXPIRED,
                    provider_invoice_id=730 + offset,
                    provider_expires_at=self.now,
                    rub_amount=Decimal("99.00"),
                )
                validated = self.make_payment(
                    intent_id=intent.pk,
                    invoice_id=730 + offset,
                )

                with self.captureOnCommitCallbacks(execute=True):
                    result = self.service(payment=validated)

                self.assertTrue(result.fulfilled)
                stored = Payment.objects.get(
                    provider=PaymentProviderEnum.CRYPTO_PAY,
                    charge_id=str(730 + offset),
                    kind=kind,
                )
                self.assertEqual(stored.user, self.initiator)
                if kind == PaymentKindEnum.SUBSCRIPTION:
                    self.assertEqual(MTPRotoKey.objects.get().user, self.initiator)
                elif kind == PaymentKindEnum.VPN_SUBSCRIPTION:
                    self.assertEqual(
                        VPNSubscription.objects.get().user,
                        self.initiator,
                    )
                else:
                    self.assertEqual(
                        GiftCertificate.objects.get().buyer,
                        self.initiator,
                    )

                if kind != PaymentKindEnum.VPN_SUBSCRIPTION:
                    purchase = AppleCashbackPurchase.objects.get(payment=stored)
                    self.assertEqual(purchase.apples_earned, 5)
                    self.assertEqual(purchase.rate_percent, 5)

                duplicate = self.service(payment=validated)
                self.assertTrue(duplicate.already_fulfilled)
                self.assertEqual(
                    Payment.objects.filter(charge_id=str(730 + offset)).count(),
                    1,
                )

        self.assertEqual(self.enqueue_notification.call_count, 3)
        self.initiator.refresh_from_db()
        self.assertEqual(self.initiator.apple_balance, 10)
        self.assertEqual(AppleCashbackPurchase.objects.count(), 2)
        push_key.assert_called_once()

    def test_historical_subscription_and_gift_replays_finalize_without_delivery(
        self,
    ) -> None:
        cases = (
            PaymentKindEnum.SUBSCRIPTION,
            PaymentKindEnum.GIFT_CERTIFICATE,
        )

        for offset, kind in enumerate(cases, start=1):
            with self.subTest(kind=kind):
                user = SystemUserFactory(username=f"historical-crypto-{offset}")
                invoice_id = 760 + offset
                payment = PaymentFactory(
                    user=user,
                    provider=PaymentProviderEnum.CRYPTO_PAY,
                    charge_id=str(invoice_id),
                    kind=kind,
                )
                if kind == PaymentKindEnum.GIFT_CERTIFICATE:
                    GiftCertificateFactory(buyer=user, payment=payment)
                AppleCashbackPurchaseFactory(
                    payment=payment,
                    identity_key=f"crypto_pay:{invoice_id}:{kind}",
                    rate_percent=None,
                    apples_earned=0,
                    balance_after=0,
                    eligible_purchase_count_after=1,
                    result_expired_at=None,
                )
                intent = CryptoPaymentIntentFactory(
                    initiator=user,
                    purchase_kind=kind,
                    status=CryptoPaymentIntentStatusEnum.ACTIVE,
                    provider_invoice_id=invoice_id,
                    rub_amount=Decimal("99.00"),
                )
                validated = self.make_payment(
                    intent_id=intent.pk,
                    invoice_id=invoice_id,
                )

                with self.captureOnCommitCallbacks(execute=True) as callbacks:
                    applied = self.service(payment=validated)
                duplicate = self.service(payment=validated)

                intent.refresh_from_db()
                user.refresh_from_db()
                self.assertTrue(applied.fulfilled)
                self.assertTrue(duplicate.already_fulfilled)
                self.assertEqual(intent.status, CryptoPaymentIntentStatusEnum.FULFILLED)
                self.assertEqual(intent.payment, payment)
                self.assertEqual(callbacks, [])
                self.assertEqual(user.apple_balance, 0)
                self.assertFalse(MTPRotoKey.objects.filter(user=user).exists())
                self.assertEqual(
                    Payment.objects.filter(user=user).count(),
                    1,
                )
                self.assertEqual(
                    AppleCashbackPurchase.objects.filter(payment__user=user).count(),
                    1,
                )

        self.enqueue_notification.assert_not_called()

    def test_active_and_retryable_intents_are_claimed(self) -> None:
        for offset, status in enumerate(
            (
                CryptoPaymentIntentStatusEnum.ACTIVE,
                CryptoPaymentIntentStatusEnum.RETRYABLE,
            ),
            start=1,
        ):
            with self.subTest(status=status):
                user = SystemUserFactory()
                intent = CryptoPaymentIntentFactory(
                    initiator=user,
                    status=status,
                    last_error_code="previous_fulfillment_error",
                    provider_invoice_id=800 + offset,
                )

                self.service(
                    payment=self.make_payment(
                        intent_id=intent.pk,
                        invoice_id=800 + offset,
                    )
                )

                intent.refresh_from_db()
                self.assertEqual(intent.status, CryptoPaymentIntentStatusEnum.FULFILLED)
                self.assertEqual(intent.last_error_code, "")

    def test_processing_intent_is_retryable_without_domain_call(self) -> None:
        intent = CryptoPaymentIntentFactory(
            initiator=self.initiator,
            status=CryptoPaymentIntentStatusEnum.PROCESSING,
            provider_invoice_id=901,
        )

        with self.assertRaises(CryptoPaymentRetryable) as raised:
            self.service(
                payment=self.make_payment(intent_id=intent.pk, invoice_id=901)
            )

        self.assertEqual(raised.exception.context["reason_code"], "processing")
        self.assertEqual(Payment.objects.count(), 0)

    def test_missing_paid_at_rolls_back_product_and_marks_retryable(self) -> None:
        intent = CryptoPaymentIntentFactory(
            initiator=self.initiator,
            status=CryptoPaymentIntentStatusEnum.ACTIVE,
            provider_invoice_id=902,
        )

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with self.assertRaises(CryptoPaymentRetryable) as raised:
                self.service(
                    payment=self.make_payment(
                        intent_id=intent.pk,
                        invoice_id=902,
                        paid=False,
                    )
                )

        intent.refresh_from_db()
        self.assertEqual(raised.exception.context["reason_code"], "paid_at_missing")
        self.assertEqual(intent.status, CryptoPaymentIntentStatusEnum.RETRYABLE)
        self.assertEqual(intent.last_error_code, "fulfillment_retryable")
        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(MTPRotoKey.objects.count(), 0)
        self.assertEqual(callbacks, [])
        self.enqueue_notification.assert_not_called()

    def test_operational_error_marks_retryable_and_is_reraised(self) -> None:
        intent = CryptoPaymentIntentFactory(
            initiator=self.initiator,
            status=CryptoPaymentIntentStatusEnum.ACTIVE,
            provider_invoice_id=903,
        )
        service = ApplyCryptoPaymentService(
            create_payment_service=mock.Mock(side_effect=OperationalError("locked")),
            fulfill_vpn_purchase_service=self.service.fulfill_vpn_purchase_service,
            create_gift_certificate_service=self.service.create_gift_certificate_service,
            enqueue_notification=self.enqueue_notification,
            clock=lambda: self.now,
        )

        with self.assertRaises(OperationalError):
            service(payment=self.make_payment(intent_id=intent.pk, invoice_id=903))

        intent.refresh_from_db()
        self.assertEqual(intent.status, CryptoPaymentIntentStatusEnum.RETRYABLE)
        self.assertEqual(Payment.objects.count(), 0)

    def test_keys_limit_failure_is_normalized_and_marks_retryable(self) -> None:
        intent = CryptoPaymentIntentFactory(
            initiator=self.initiator,
            status=CryptoPaymentIntentStatusEnum.ACTIVE,
            provider_invoice_id=905,
        )
        service = ApplyCryptoPaymentService(
            create_payment_service=mock.Mock(
                side_effect=KeysLimitReached(self.initiator.username)
            ),
            fulfill_vpn_purchase_service=self.service.fulfill_vpn_purchase_service,
            create_gift_certificate_service=self.service.create_gift_certificate_service,
            enqueue_notification=self.enqueue_notification,
            clock=lambda: self.now,
        )

        with self.assertRaises(CryptoPaymentRetryable) as raised:
            service(payment=self.make_payment(intent_id=intent.pk, invoice_id=905))

        intent.refresh_from_db()
        self.assertEqual(raised.exception.context["reason_code"], "fulfillment_retryable")
        self.assertEqual(intent.status, CryptoPaymentIntentStatusEnum.RETRYABLE)
        self.assertEqual(intent.last_error_code, "fulfillment_retryable")
        self.assertEqual(Payment.objects.count(), 0)

    def test_callbacks_do_not_run_before_outer_commit(self) -> None:
        intent = CryptoPaymentIntentFactory(
            initiator=self.initiator,
            purchase_kind=PaymentKindEnum.VPN_SUBSCRIPTION,
            product_code=ProductCodeEnum.VPN_30D,
            status=CryptoPaymentIntentStatusEnum.ACTIVE,
            provider_invoice_id=904,
        )

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self.service(
                payment=self.make_payment(intent_id=intent.pk, invoice_id=904)
            )
            self.schedule_profiles.assert_not_called()
            self.enqueue_notification.assert_not_called()

        for callback in callbacks:
            callback()

        self.schedule_profiles.assert_called_once()
        self.enqueue_notification.assert_called_once_with(intent_id=intent.pk)


class TestApplyCryptoPaymentConcurrency(ApplyCryptoPaymentServiceMixin, TransactionTestCase):
    def test_concurrent_apply_creates_one_product_and_payment(self) -> None:
        initiator = SystemUserFactory(username="987654321")
        intent = CryptoPaymentIntentFactory(
            initiator=initiator,
            status=CryptoPaymentIntentStatusEnum.ACTIVE,
            provider_invoice_id=990,
        )
        service = self.build_service()
        validated = self.make_payment(intent_id=intent.pk, invoice_id=990)

        def apply() -> str:
            close_old_connections()
            try:
                result = service(payment=validated)
            except (CryptoPaymentRetryable, OperationalError):
                return "retry"
            finally:
                close_old_connections()
            return "fulfilled" if result.fulfilled else "duplicate"

        with mock.patch(
            "apps.vds.services.issue_key_service.push_key_to_servers_task"
        ), ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: apply(), range(2)))

        self.assertIn("fulfilled", outcomes)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(MTPRotoKey.objects.count(), 1)

    def test_retryable_state_write_recovers_after_held_sqlite_lock(self) -> None:
        intent = CryptoPaymentIntentFactory(
            status=CryptoPaymentIntentStatusEnum.ACTIVE,
            provider_invoice_id=991,
        )
        service = self.build_service()
        start_lock = Event()
        locked = Event()
        release = Event()

        def hold_write_lock() -> None:
            close_old_connections()
            try:
                start_lock.wait(timeout=1)
                with transaction.atomic():
                    type(intent).objects.filter(pk=intent.pk).update(
                        last_error_code="lock_holder"
                    )
                    locked.set()
                    release.wait(timeout=2)
            finally:
                close_old_connections()

        from apps.payments.selectors import (
            conditionally_transition_crypto_intent,
            get_crypto_intent_by_id,
        )

        def get_then_lock(**kwargs):
            current = get_crypto_intent_by_id(**kwargs)
            if not start_lock.is_set():
                start_lock.set()
                self.assertTrue(locked.wait(timeout=1))
            return current

        def transition_after_contention(**kwargs):
            try:
                return conditionally_transition_crypto_intent(**kwargs)
            except OperationalError:
                release.set()
                raise

        with connection.cursor() as cursor:
            cursor.execute("PRAGMA busy_timeout = 50")
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(hold_write_lock)
            with mock.patch(
                "apps.payments.services.apply_crypto_payment.get_crypto_intent_by_id",
                side_effect=get_then_lock,
            ), mock.patch(
                "apps.payments.services.apply_crypto_payment."
                "conditionally_transition_crypto_intent",
                side_effect=transition_after_contention,
            ) as retry_write:
                with self.assertRaises(OperationalError):
                    service(
                        payment=self.make_payment(
                            intent_id=intent.pk,
                            invoice_id=991,
                        )
                    )
            release.set()
            future.result(timeout=2)

        intent.refresh_from_db()
        self.assertGreaterEqual(retry_write.call_count, 2)
        self.assertEqual(intent.status, CryptoPaymentIntentStatusEnum.RETRYABLE)
