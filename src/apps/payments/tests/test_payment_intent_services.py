from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock

from django.test import TestCase
from django.utils import timezone

from apps.payments.enums import (
    PaymentIntentStatusEnum,
    PaymentProviderEnum,
    ProductCodeEnum,
)
from apps.payments.exceptions import (
    BadPaymentData,
    PaymentIntentExpired,
    PaymentIntentMismatch,
    PaymentIntentNotFound,
    VPNProductNotConfigured,
)
from apps.payments.models import PaymentIntent
from apps.payments.services.dtos import (
    CreatePaymentIntentIn,
    PreCheckoutPaymentIntentIn,
)
from apps.payments.services.payment_intents import (
    ApprovePaymentIntentService,
    CreatePaymentIntentService,
)
from apps.payments.tests.factories import PaymentIntentFactory, ProductFactory
from apps.users.tests.factories import SystemUserFactory
from apps.vpn.exceptions import VPNCapacityUnavailable


class CreatePaymentIntentServiceTest(TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory(username="123")
        self.product = ProductFactory(
            code=ProductCodeEnum.VLESS_30D,
            price=Decimal("199.00"),
            stars_price=150,
            currency="RUB",
        )
        self.availability = Mock()
        self.now = timezone.now()
        self.service = CreatePaymentIntentService(
            check_sale_availability=self.availability,
            get_product=Mock(return_value=self.product),
            get_user=Mock(return_value=self.user),
            now=Mock(return_value=self.now),
            intent_ttl=timedelta(minutes=15),
        )

    def test_creates_exact_immutable_rub_intent(self) -> None:
        result = self.service(
            intent=CreatePaymentIntentIn(username="123", currency="RUB")
        )

        stored = PaymentIntent.objects.get(pk=result.intent_id)
        self.assertEqual(stored.user, self.user)
        self.assertEqual(stored.product, self.product)
        self.assertEqual(stored.currency, "RUB")
        self.assertEqual(stored.amount, 19_900)
        self.assertEqual(stored.provider, PaymentProviderEnum.YUKASSA)
        self.assertEqual(stored.expires_at, self.now + timedelta(minutes=15))
        self.assertEqual(stored.status, PaymentIntentStatusEnum.CREATED)
        self.assertEqual(result.invoice_payload, stored.invoice_payload)
        self.availability.assert_called_once_with(customer=self.user)

    def test_creates_exact_stars_intent(self) -> None:
        result = self.service(
            intent=CreatePaymentIntentIn(username="123", currency="XTR")
        )

        stored = PaymentIntent.objects.get(pk=result.intent_id)
        self.assertEqual(stored.currency, "XTR")
        self.assertEqual(stored.amount, 150)
        self.assertEqual(stored.provider, PaymentProviderEnum.STARS)

    def test_rejects_missing_or_partial_product_prices(self) -> None:
        invalid_products = (
            None,
            ProductFactory(code=None),
            ProductFactory(code=None, price=Decimal("0.00")),
            ProductFactory(code=None, stars_price=0),
            ProductFactory(code=None, currency="USD"),
        )

        for product in invalid_products:
            with self.subTest(product=product):
                service = CreatePaymentIntentService(
                    check_sale_availability=Mock(),
                    get_product=Mock(return_value=product),
                    get_user=Mock(return_value=self.user),
                    now=Mock(return_value=self.now),
                    intent_ttl=timedelta(minutes=15),
                )
                with self.assertRaises(VPNProductNotConfigured):
                    service(
                        intent=CreatePaymentIntentIn(username="123", currency="RUB")
                    )

    def test_rejects_unknown_currency_or_user(self) -> None:
        with self.assertRaises(BadPaymentData):
            self.service(intent=CreatePaymentIntentIn(username="123", currency="USD"))

        service = CreatePaymentIntentService(
            check_sale_availability=Mock(),
            get_product=Mock(return_value=self.product),
            get_user=Mock(return_value=None),
            now=Mock(return_value=self.now),
            intent_ttl=timedelta(minutes=15),
        )
        with self.assertRaises(BadPaymentData):
            service(intent=CreatePaymentIntentIn(username="missing", currency="RUB"))

    def test_does_not_create_intent_when_availability_rejects(self) -> None:
        self.availability.side_effect = VPNCapacityUnavailable("123")

        with self.assertRaises(VPNCapacityUnavailable):
            self.service(intent=CreatePaymentIntentIn(username="123", currency="RUB"))

        self.assertEqual(PaymentIntent.objects.count(), 0)


class ApprovePaymentIntentServiceTest(TestCase):
    def setUp(self) -> None:
        self.now = timezone.now()
        self.intent = PaymentIntentFactory(
            user__username="123",
            product__code=ProductCodeEnum.VLESS_30D,
            currency="RUB",
            amount=19_900,
            provider=PaymentProviderEnum.YUKASSA,
            expires_at=self.now + timedelta(minutes=1),
        )
        self.availability = Mock()
        self.service = ApprovePaymentIntentService(
            check_sale_availability=self.availability,
            get_intent=Mock(return_value=self.intent),
            now=Mock(return_value=self.now),
        )
        self.data = PreCheckoutPaymentIntentIn(
            username="123",
            invoice_payload=self.intent.invoice_payload,
            currency="RUB",
            amount=19_900,
        )

    def test_approves_exact_created_intent_after_current_availability_check(
        self,
    ) -> None:
        result = self.service(pre_checkout=self.data)

        self.intent.refresh_from_db()
        self.assertEqual(self.intent.status, PaymentIntentStatusEnum.APPROVED)
        self.assertEqual(result.intent_id, self.intent.pk)
        self.availability.assert_called_once_with(customer=self.intent.user)

    def test_exact_approved_retry_is_idempotent_without_rechecking_availability(
        self,
    ) -> None:
        self.intent.transition_to(status=PaymentIntentStatusEnum.APPROVED)
        self.availability.side_effect = VPNCapacityUnavailable("123")

        first = self.service(pre_checkout=self.data)
        second = self.service(pre_checkout=self.data)

        self.assertEqual(first, second)
        self.availability.assert_not_called()

    def test_rejects_state_change_between_invoice_and_precheckout(self) -> None:
        self.availability.side_effect = VPNCapacityUnavailable("123")

        with self.assertRaises(VPNCapacityUnavailable):
            self.service(pre_checkout=self.data)

        self.intent.refresh_from_db()
        self.assertEqual(self.intent.status, PaymentIntentStatusEnum.CREATED)

    def test_rejects_expired_created_intent(self) -> None:
        service = ApprovePaymentIntentService(
            check_sale_availability=Mock(),
            get_intent=Mock(return_value=self.intent),
            now=Mock(return_value=self.intent.expires_at),
        )

        with self.assertRaises(PaymentIntentExpired):
            service(pre_checkout=self.data)

    def test_rejects_unknown_or_mismatched_intent(self) -> None:
        missing = ApprovePaymentIntentService(
            check_sale_availability=Mock(),
            get_intent=Mock(return_value=None),
            now=Mock(return_value=self.now),
        )
        with self.assertRaises(PaymentIntentNotFound):
            missing(pre_checkout=self.data)

        mismatches = (
            {"username": "other"},
            {"currency": "XTR"},
            {"amount": 19_901},
        )
        for changes in mismatches:
            with self.subTest(changes=changes):
                values = {
                    "username": "123",
                    "invoice_payload": self.intent.invoice_payload,
                    "currency": "RUB",
                    "amount": 19_900,
                    **changes,
                }
                with self.assertRaises(PaymentIntentMismatch):
                    self.service(pre_checkout=PreCheckoutPaymentIntentIn(**values))
