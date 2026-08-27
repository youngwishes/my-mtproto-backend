from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.payments.enums import PaymentKindEnum, PaymentProviderEnum, ProductCodeEnum
from apps.payments.exceptions import BadPaymentData
from apps.payments.models import AppleCashbackPurchase, GiftCertificate, Payment
from apps.payments.services import (
    get_create_gift_certificate_service,
    get_create_payment_service,
)
from apps.payments.services.dtos import (
    ApplePurchaseOutcomeDTO,
    CreateGiftCertificateIn,
    CreateGiftCertificateOut,
    CreatePaymentIn,
    CreatePaymentOut,
    HistoricalPurchaseReplayDTO,
)
from apps.payments.tests.factories import (
    AppleCashbackPurchaseFactory,
    GiftCertificateFactory,
    PaymentFactory,
    ProductFactory,
)
from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import MTPRotoKey


class AppleCashbackPurchaseTestMixin:
    def _seed_historical_purchases(self, *, user, count: int) -> None:
        for ordinal in range(1, count + 1):
            AppleCashbackPurchaseFactory(
                payment__user=user,
                payment__charge_id=f"historical-{user.pk}-{ordinal}",
                identity_key=f"stars:historical-{user.pk}-{ordinal}:subscription",
                rate_percent=None,
                apples_earned=0,
                balance_after=0,
                eligible_purchase_count_after=ordinal,
                result_expired_at=None,
            )


class TestSubscriptionAppleCashback(AppleCashbackPurchaseTestMixin, TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory(username="cashback-subscription")
        self.product = ProductFactory(
            code=ProductCodeEnum.MTPROTO_30D,
            price=Decimal("9900"),
            currency="RUB",
        )
        self.service = get_create_payment_service()

    def _payment(
        self,
        *,
        username: str | None = None,
        charge_id: str = "subscription-charge",
        provider: str = PaymentProviderEnum.STARS,
    ) -> CreatePaymentIn:
        return CreatePaymentIn(
            username=username or self.user.username,
            charge_id=charge_id,
            provider=provider,
        )

    def test_uses_pre_purchase_rate_at_both_level_transitions(self) -> None:
        cases = (
            (3, 5, 4, "Садовник", True, 10),
            (6, 10, 7, "Мастер сада", True, 15),
            (7, 15, 8, "Мастер сада", False, 15),
        )

        for previous_count, earned, resulting_count, level, level_up, next_rate in cases:
            with self.subTest(previous_count=previous_count):
                user = SystemUserFactory(username=f"transition-{previous_count}")
                self._seed_historical_purchases(user=user, count=previous_count)

                result = self.service(
                    payment=self._payment(
                        username=user.username,
                        charge_id=f"transition-charge-{previous_count}",
                    )
                )

                self.assertIsInstance(result, CreatePaymentOut)
                self.assertEqual(
                    result.loyalty,
                    ApplePurchaseOutcomeDTO(
                        apples_earned=earned,
                        rate_percent={3: 5, 6: 10, 7: 15}[previous_count],
                        balance=earned,
                        eligible_purchase_count=resulting_count,
                        level=level,
                        level_up=level_up,
                        next_purchase_rate_percent=next_rate,
                    ),
                )

    def test_catalog_price_uses_half_up_rounding(self) -> None:
        self.product.price = Decimal("1000")
        self.product.save(update_fields=["price"])

        result = self.service(payment=self._payment(charge_id="half-up"))

        self.assertEqual(result.loyalty.apples_earned, 1)
        self.assertEqual(result.loyalty.rate_percent, 5)

    def test_post_launch_duplicate_returns_saved_outcome_without_second_effect(self) -> None:
        original_expiry = timezone.now() + timedelta(days=10)
        key = MTPRotoKey.objects.create(
            user=self.user,
            token="duplicate-token",
            expired_date=original_expiry,
        )

        first = self.service(payment=self._payment(charge_id="same-charge"))
        key.refresh_from_db()
        first_expiry = key.expired_date
        second = self.service(payment=self._payment(charge_id="same-charge"))

        key.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(second, first)
        self.assertEqual(key.expired_date, first_expiry)
        self.assertEqual(self.user.apple_balance, 5)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(AppleCashbackPurchase.objects.count(), 1)

    @mock.patch("apps.core.decorators._log_service_error")
    def test_duplicate_owned_by_another_user_is_rejected_without_mutation(
        self, _mock_log: mock.Mock
    ) -> None:
        first = self.service(payment=self._payment(charge_id="foreign-charge"))
        owner_expiry = first.expired_date
        stranger = SystemUserFactory(username="cashback-stranger")

        with self.assertRaises(BadPaymentData):
            self.service(
                payment=self._payment(
                    username=stranger.username,
                    charge_id="foreign-charge",
                )
            )

        stranger.refresh_from_db()
        self.assertEqual(stranger.apple_balance, 0)
        self.assertEqual(MTPRotoKey.objects.count(), 1)
        self.assertEqual(
            MTPRotoKey.objects.get(user=self.user).expired_date.date().strftime("%d.%m.%y"),
            owner_expiry,
        )
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(AppleCashbackPurchase.objects.count(), 1)

    @mock.patch("apps.core.decorators._log_service_error")
    def test_empty_charge_id_is_rejected_before_any_effect(
        self, _mock_log: mock.Mock
    ) -> None:
        with self.assertRaises(BadPaymentData):
            self.service(payment=self._payment(charge_id="   "))

        self.user.refresh_from_db()
        self.assertEqual(self.user.apple_balance, 0)
        self.assertEqual(MTPRotoKey.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(AppleCashbackPurchase.objects.count(), 0)

    @mock.patch(
        "apps.payments.services.create_payment_service._saved_subscription_result",
        side_effect=RuntimeError("outcome failed"),
    )
    def test_post_persistence_failure_rolls_back_all_purchase_effects(
        self, _mock_saved_result: mock.Mock
    ) -> None:
        original_expiry = timezone.now() + timedelta(days=10)
        key = MTPRotoKey.objects.create(
            user=self.user,
            token="rollback-token",
            expired_date=original_expiry,
        )
        self._seed_historical_purchases(user=self.user, count=1)
        self.user.apple_balance = 7
        self.user.save(update_fields=["apple_balance"])
        payment_count_before = Payment.objects.count()
        purchase_count_before = AppleCashbackPurchase.objects.count()

        with self.assertRaisesRegex(RuntimeError, "outcome failed"):
            self.service(payment=self._payment(charge_id="failed-charge"))

        key.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(
            (
                key.expired_date,
                self.user.apple_balance,
                MTPRotoKey.objects.count(),
                Payment.objects.count(),
                AppleCashbackPurchase.objects.count(),
                Payment.objects.filter(
                    provider=PaymentProviderEnum.STARS,
                    charge_id="failed-charge",
                    kind=PaymentKindEnum.SUBSCRIPTION,
                ).exists(),
                AppleCashbackPurchase.objects.filter(
                    identity_key="stars:failed-charge:subscription"
                ).exists(),
                AppleCashbackPurchase.objects.filter(
                    payment__user=self.user
                ).count(),
            ),
            (
                original_expiry,
                7,
                1,
                payment_count_before,
                purchase_count_before,
                False,
                False,
                1,
            ),
        )

    def test_pre_launch_replay_returns_only_tag_without_mutation(self) -> None:
        payment = PaymentFactory(
            user=self.user,
            provider=PaymentProviderEnum.STARS,
            charge_id="historical-charge",
            kind=PaymentKindEnum.SUBSCRIPTION,
        )
        AppleCashbackPurchaseFactory(
            payment=payment,
            identity_key="stars:historical-charge:subscription",
            rate_percent=None,
            apples_earned=0,
            balance_after=0,
            eligible_purchase_count_after=1,
            result_expired_at=None,
        )

        result = self.service(
            payment=self._payment(charge_id="historical-charge")
        )

        self.assertEqual(result, HistoricalPurchaseReplayDTO())
        self.assertEqual(result.asdict(), {"kind": "historical_replay"})
        self.user.refresh_from_db()
        self.assertEqual(self.user.apple_balance, 0)
        self.assertEqual(MTPRotoKey.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(AppleCashbackPurchase.objects.count(), 1)

    def test_vpn_payment_does_not_change_rate_or_gain_loyalty(self) -> None:
        vpn_payment = PaymentFactory(
            user=self.user,
            provider=PaymentProviderEnum.STARS,
            charge_id="vpn-charge",
            kind=PaymentKindEnum.VPN_SUBSCRIPTION,
        )

        result = self.service(payment=self._payment(charge_id="eligible-after-vpn"))

        self.assertEqual(result.loyalty.rate_percent, 5)
        self.assertEqual(result.loyalty.eligible_purchase_count, 1)
        self.assertFalse(
            AppleCashbackPurchase.objects.filter(payment=vpn_payment).exists()
        )


class TestGiftCertificateAppleCashback(AppleCashbackPurchaseTestMixin, TestCase):
    def setUp(self) -> None:
        self.buyer = SystemUserFactory(username="cashback-gift-buyer")
        ProductFactory(
            code=ProductCodeEnum.MTPROTO_30D,
            price=Decimal("9900"),
            currency="RUB",
        )
        self.service = get_create_gift_certificate_service()

    def _certificate(
        self,
        *,
        username: str | None = None,
        charge_id: str = "gift-charge",
    ) -> CreateGiftCertificateIn:
        return CreateGiftCertificateIn(
            username=username or self.buyer.username,
            charge_id=charge_id,
            provider=PaymentProviderEnum.STARS,
        )

    def test_gift_credits_the_buyer_and_returns_code_with_loyalty(self) -> None:
        result = self.service(certificate=self._certificate())

        self.assertIsInstance(result, CreateGiftCertificateOut)
        self.assertEqual(result.code, GiftCertificate.objects.get().code)
        self.assertEqual(
            result.loyalty,
            ApplePurchaseOutcomeDTO(
                apples_earned=5,
                rate_percent=5,
                balance=5,
                eligible_purchase_count=1,
                level="Новичок",
                level_up=False,
                next_purchase_rate_percent=5,
            ),
        )
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.apple_balance, 5)

    def test_gift_duplicate_returns_saved_code_and_loyalty_without_second_effect(self) -> None:
        first = self.service(certificate=self._certificate(charge_id="gift-duplicate"))
        second = self.service(certificate=self._certificate(charge_id="gift-duplicate"))

        self.assertEqual(second, first)
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.apple_balance, 5)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(GiftCertificate.objects.count(), 1)
        self.assertEqual(AppleCashbackPurchase.objects.count(), 1)

    def test_historical_gift_replay_returns_only_tag_without_mutation(self) -> None:
        payment = PaymentFactory(
            user=self.buyer,
            provider=PaymentProviderEnum.STARS,
            charge_id="historical-gift",
            kind=PaymentKindEnum.GIFT_CERTIFICATE,
        )
        GiftCertificateFactory(
            buyer=self.buyer,
            payment=payment,
            code="KEY-HIST-GIFT",
        )
        AppleCashbackPurchaseFactory(
            payment=payment,
            identity_key="stars:historical-gift:gift_certificate",
            rate_percent=None,
            apples_earned=0,
            balance_after=0,
            eligible_purchase_count_after=1,
            result_expired_at=None,
        )

        result = self.service(
            certificate=self._certificate(charge_id="historical-gift")
        )

        self.assertEqual(result, HistoricalPurchaseReplayDTO())
        self.assertEqual(result.asdict(), {"kind": "historical_replay"})
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.apple_balance, 0)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(GiftCertificate.objects.count(), 1)
        self.assertEqual(AppleCashbackPurchase.objects.count(), 1)
