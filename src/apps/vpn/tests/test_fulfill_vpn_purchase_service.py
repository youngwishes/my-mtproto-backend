from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.payments.enums import PaymentKindEnum, PaymentProviderEnum, ProductCodeEnum
from apps.payments.models import Payment
from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory
from apps.vpn.models import VPNSubscription
from apps.vpn.services.fulfill_vpn_purchase_service import FulfillVPNPurchaseService
from apps.vpn.services.dtos import FulfillVPNPaymentIn
from apps.vpn.tests.factories import VPNSubscriptionFactory


class TestFulfillVPNPurchaseService(TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory(username="12345678")
        self.scheduler = mock.Mock()
        self.service = FulfillVPNPurchaseService(
            schedule_profiles=self.scheduler,
            subscription_base_url="https://vpn.example.com",
        )

    def _payment(
        self,
        *,
        charge_id: str = "charge-1",
        provider: str = PaymentProviderEnum.STARS,
    ) -> FulfillVPNPaymentIn:
        return FulfillVPNPaymentIn(
            username=self.user.username,
            charge_id=charge_id,
            provider=provider,
            product_code=ProductCodeEnum.VPN_30D,
        )

    def test_first_purchase_creates_subscription_and_payment(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            result = self.service(payment=self._payment())

        subscription = VPNSubscription.objects.get(user=self.user)
        payment = Payment.objects.get()
        self.assertAlmostEqual(
            subscription.expired_at,
            timezone.now() + timedelta(days=30),
            delta=timedelta(seconds=5),
        )
        self.assertEqual(payment.user, self.user)
        self.assertIsNone(payment.key)
        self.assertEqual(payment.kind, PaymentKindEnum.VPN_SUBSCRIPTION)
        self.assertEqual(result.expired_at, subscription.expired_at)
        self.assertEqual(
            result.subscription_url,
            f"https://vpn.example.com/api/v1/vpn/subscriptions/{subscription.token}/",
        )
        self.scheduler.assert_called_once_with(subscription_id=subscription.pk)

    def test_active_subscription_is_extended_by_thirty_days(self) -> None:
        subscription = VPNSubscriptionFactory(
            user=self.user,
            expired_at=timezone.now() + timedelta(days=10),
        )
        previous_expired_at = subscription.expired_at

        with self.captureOnCommitCallbacks(execute=True):
            result = self.service(payment=self._payment())

        subscription.refresh_from_db()
        self.assertEqual(subscription.expired_at, previous_expired_at + timedelta(days=30))
        self.assertEqual(result.expired_at, subscription.expired_at)

    def test_distinct_payments_extend_subscription_once_each(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            self.service(payment=self._payment(charge_id="charge-1"))
        with self.captureOnCommitCallbacks(execute=True):
            self.service(payment=self._payment(charge_id="charge-2"))

        subscription = VPNSubscription.objects.get(user=self.user)
        self.assertEqual(Payment.objects.filter(user=self.user).count(), 2)
        self.assertAlmostEqual(
            subscription.expired_at,
            timezone.now() + timedelta(days=60),
            delta=timedelta(seconds=5),
        )

    def test_expired_or_inactive_subscription_restarts_from_payment_time(self) -> None:
        for expired_at, is_active in (
            (timezone.now() - timedelta(days=1), True),
            (timezone.now() + timedelta(days=10), False),
        ):
            with self.subTest(expired_at=expired_at, is_active=is_active):
                subscription = VPNSubscriptionFactory(
                    user=SystemUserFactory(),
                    expired_at=expired_at,
                    is_active=is_active,
                )
                payment = FulfillVPNPaymentIn(
                    username=subscription.user.username,
                    charge_id=f"restart-{subscription.pk}",
                    provider=PaymentProviderEnum.STARS,
                    product_code=ProductCodeEnum.VPN_30D,
                )

                with self.captureOnCommitCallbacks(execute=True):
                    self.service(payment=payment)

                subscription.refresh_from_db()
                self.assertTrue(subscription.is_active)
                self.assertAlmostEqual(
                    subscription.expired_at,
                    timezone.now() + timedelta(days=30),
                    delta=timedelta(seconds=5),
                )

    def test_renewal_preserves_subscription_token_and_credentials(self) -> None:
        subscription = VPNSubscriptionFactory(user=self.user)
        credentials = (
            subscription.token,
            subscription.vless_uuid,
            subscription.hysteria_secret,
        )

        with self.captureOnCommitCallbacks(execute=True):
            self.service(payment=self._payment())

        subscription.refresh_from_db()
        self.assertEqual(
            (subscription.token, subscription.vless_uuid, subscription.hysteria_secret),
            credentials,
        )

    def test_repeated_provider_charge_does_not_extend_twice(self) -> None:
        for provider in (PaymentProviderEnum.STARS, PaymentProviderEnum.CRYPTO_PAY):
            with self.subTest(provider=provider):
                user = SystemUserFactory()
                service = FulfillVPNPurchaseService(
                    schedule_profiles=self.scheduler,
                    subscription_base_url="https://vpn.example.com",
                )
                payment = FulfillVPNPaymentIn(
                    username=user.username,
                    charge_id="duplicate-charge",
                    provider=provider,
                    product_code=ProductCodeEnum.VPN_30D,
                )

                with self.captureOnCommitCallbacks(execute=True):
                    first_result = service(payment=payment)
                with self.captureOnCommitCallbacks(execute=True):
                    duplicate_result = service(payment=payment)

                subscription = VPNSubscription.objects.get(user=user)
                self.assertEqual(Payment.objects.filter(user=user).count(), 1)
                self.assertEqual(duplicate_result, first_result)
                self.assertEqual(subscription.expired_at, first_result.expired_at)

    def test_repeated_provider_charge_returns_original_users_subscription(self) -> None:
        another_user = SystemUserFactory()
        with self.captureOnCommitCallbacks(execute=True):
            first_result = self.service(payment=self._payment())

        duplicate_payment = FulfillVPNPaymentIn(
            username=another_user.username,
            charge_id="charge-1",
            provider=PaymentProviderEnum.STARS,
            product_code=ProductCodeEnum.VPN_30D,
        )
        duplicate_result = self.service(payment=duplicate_payment)

        self.assertEqual(duplicate_result, first_result)
        self.assertEqual(VPNSubscription.objects.count(), 1)

    def test_vpn_purchase_does_not_change_mtproto_key(self) -> None:
        key = MTPRotoKeyFactory(user=self.user)
        previous_expired_date = key.expired_date

        with self.captureOnCommitCallbacks(execute=True):
            self.service(payment=self._payment())

        key.refresh_from_db()
        self.assertEqual(key.expired_date, previous_expired_date)
