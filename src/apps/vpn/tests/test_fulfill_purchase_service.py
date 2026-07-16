from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock

from django.test import TestCase
from django.utils import timezone

from apps.payments.enums import ProductCodeEnum
from apps.payments.models import GiftCertificate, Payment
from apps.payments.services.dtos import VPNPaymentFulfillmentIn
from apps.payments.tests.factories import PaymentFactory, ProductFactory
from apps.vds.models import MTPRotoKey
from apps.vds.tests.factories import MTPRotoKeyFactory
from apps.vpn.enums import VPNAccessState
from apps.vpn.models import VPNAccess, VPNPurchase
from apps.vpn.services.fulfill_purchase import FulfillPurchaseService
from apps.vpn.tests.factories import VPNAccessFactory


class FulfillPurchaseServiceTest(TestCase):
    def setUp(self) -> None:
        self.accepted_at = timezone.now()
        self.product = ProductFactory(code=ProductCodeEnum.VLESS_30D)
        self.payment = PaymentFactory(product=self.product, key=None)
        self.callbacks: list[object] = []
        self.scheduled: list[int] = []
        self.service = self._service()

    def _service(self, **overrides: object) -> FulfillPurchaseService:
        values = {
            "get_access": lambda *, user_id: VPNAccess.objects.filter(user_id=user_id).first(),
            "get_purchase": lambda *, payment_id: VPNPurchase.objects.filter(payment_id=payment_id).select_related("access").first(),
            "create_access": VPNAccess.objects.create,
            "save_access": lambda *, access, update_fields: access.save(update_fields=update_fields),
            "create_purchase": VPNPurchase.objects.create,
            "register_after_commit": self.callbacks.append,
            "schedule_delivery": lambda *, access_id: self.scheduled.append(access_id),
        }
        values.update(overrides)
        return FulfillPurchaseService(**values)

    def _purchase(self, *, payment: Payment | None = None) -> VPNPaymentFulfillmentIn:
        selected = payment or self.payment
        return VPNPaymentFulfillmentIn(
            receipt_id=101,
            payment_id=selected.pk,
            user_id=selected.user_id,
            accepted_at=self.accepted_at,
        )

    def test_first_purchase_creates_one_access_and_30_day_audit(self) -> None:
        result = self.service(purchase=self._purchase())

        access = VPNAccess.objects.get(pk=result.access_id)
        purchase = VPNPurchase.objects.get(pk=result.purchase_id)
        self.assertEqual(access.user, self.payment.user)
        self.assertEqual(access.expired_at, self.accepted_at + timedelta(days=30))
        self.assertEqual(access.state, VPNAccessState.PREPARING)
        self.assertEqual(purchase.payment, self.payment)
        self.assertEqual(purchase.period_days, 30)
        self.assertEqual(purchase.expired_at_after, access.expired_at)

    def test_active_renewal_adds_30_days_from_current_expiry(self) -> None:
        current_expiry = self.accepted_at + timedelta(days=9)
        access = VPNAccessFactory(
            user=self.payment.user,
            expired_at=current_expiry,
            state=VPNAccessState.PREPARING,
        )
        token = access.subscription_token
        desired_uuid = access.desired_uuid

        self.service(purchase=self._purchase())

        access.refresh_from_db()
        self.assertEqual(access.expired_at, current_expiry + timedelta(days=30))
        self.assertEqual(access.subscription_token, token)
        self.assertEqual(access.desired_uuid, desired_uuid)

    def test_expired_renewal_starts_at_acceptance_and_reenters_preparing(self) -> None:
        access = VPNAccessFactory(
            user=self.payment.user,
            expired_at=self.accepted_at - timedelta(days=3),
            state=VPNAccessState.EXPIRED,
        )
        token = access.subscription_token
        desired_uuid = access.desired_uuid

        self.service(purchase=self._purchase())

        access.refresh_from_db()
        self.assertEqual(access.expired_at, self.accepted_at + timedelta(days=30))
        self.assertEqual(access.state, VPNAccessState.PREPARING)
        self.assertEqual(access.state_revision, 2)
        self.assertEqual(access.subscription_token, token)
        self.assertEqual(access.desired_uuid, desired_uuid)

    def test_two_sequential_receipts_add_exactly_two_periods(self) -> None:
        second_payment = PaymentFactory(
            user=self.payment.user,
            product=self.product,
            key=None,
        )

        self.service(purchase=self._purchase())
        self.service(purchase=self._purchase(payment=second_payment))

        access = VPNAccess.objects.get(user=self.payment.user)
        self.assertEqual(access.expired_at, self.accepted_at + timedelta(days=60))
        self.assertEqual(VPNPurchase.objects.count(), 2)

    def test_same_payment_retry_is_exact_without_adding_time_or_scheduling(self) -> None:
        first = self.service(purchase=self._purchase())
        first_callback_count = len(self.callbacks)

        replay = self.service(purchase=self._purchase())

        self.assertEqual(replay, first)
        self.assertEqual(VPNPurchase.objects.count(), 1)
        self.assertEqual(len(self.callbacks), first_callback_count)

    def test_does_not_mutate_mtproto_free_referral_or_gift_state(self) -> None:
        key = MTPRotoKeyFactory(user=self.payment.user)
        before_key = (key.expired_date, key.was_deleted, key.is_active)
        before_user = (
            self.payment.user.first_month_free_used,
            self.payment.user.referral_activated,
            self.payment.user.referral_link_activated_count,
        )
        before_gifts = GiftCertificate.objects.count()

        self.service(purchase=self._purchase())

        key.refresh_from_db()
        self.payment.user.refresh_from_db()
        self.assertEqual((key.expired_date, key.was_deleted, key.is_active), before_key)
        self.assertEqual(
            (
                self.payment.user.first_month_free_used,
                self.payment.user.referral_activated,
                self.payment.user.referral_link_activated_count,
            ),
            before_user,
        )
        self.assertEqual(MTPRotoKey.objects.count(), 1)
        self.assertEqual(GiftCertificate.objects.count(), before_gifts)

    def test_purchase_failure_rolls_back_new_access_and_does_not_schedule(self) -> None:
        create_purchase = Mock(side_effect=RuntimeError("audit insert failed"))
        service = self._service(create_purchase=create_purchase)

        with self.assertRaisesRegex(RuntimeError, "audit insert failed"):
            service(purchase=self._purchase())

        self.assertFalse(VPNAccess.objects.exists())
        self.assertFalse(VPNPurchase.objects.exists())
        self.assertEqual(self.callbacks, [])

    def test_delivery_is_registered_after_commit_and_broker_failure_is_nonfatal(self) -> None:
        result = self.service(purchase=self._purchase())

        self.assertEqual(self.scheduled, [])
        self.assertEqual(len(self.callbacks), 1)
        callback = self.callbacks[0]
        callback()
        self.assertEqual(self.scheduled, [result.access_id])

        failing_service = self._service(
            register_after_commit=Mock(side_effect=RuntimeError("broker unavailable"))
        )
        second_payment = PaymentFactory(user=self.payment.user, product=self.product)
        failing_service(purchase=self._purchase(payment=second_payment))
        self.assertEqual(VPNPurchase.objects.count(), 2)
