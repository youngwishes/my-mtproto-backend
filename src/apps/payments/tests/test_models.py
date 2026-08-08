from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.payments.enums import (
    PaymentKindEnum,
    PaymentMethodCodeEnum,
    PaymentProviderEnum,
    ProductCodeEnum,
)
from apps.payments.models import PaymentMethod, Product
from apps.payments.tests.factories import PaymentFactory, ProductFactory


class TestProductModel(TestCase):
    def test_product_code_is_unique(self) -> None:
        ProductFactory(code=ProductCodeEnum.MTPROTO_30D)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProductFactory(code=ProductCodeEnum.MTPROTO_30D)


class TestPaymentModel(TestCase):
    def test_vpn_payment_identity_is_unique_per_provider_charge_and_kind(self) -> None:
        PaymentFactory(
            provider=PaymentProviderEnum.YUKASSA,
            charge_id="vpn-charge-id",
            kind=PaymentKindEnum.VPN_SUBSCRIPTION,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PaymentFactory(
                    provider=PaymentProviderEnum.YUKASSA,
                    charge_id="vpn-charge-id",
                    kind=PaymentKindEnum.VPN_SUBSCRIPTION,
                )

    def test_subscription_payment_identity_is_not_limited_by_vpn_constraint(self) -> None:
        for _ in range(2):
            PaymentFactory(
                provider=PaymentProviderEnum.YUKASSA,
                charge_id="subscription-charge-id",
                kind=PaymentKindEnum.SUBSCRIPTION,
            )


class TestPaymentMethodModel(TestCase):
    def test_code_is_unique(self) -> None:
        PaymentMethod.objects.all().delete()
        PaymentMethod.objects.create(code=PaymentMethodCodeEnum.STARS)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PaymentMethod.objects.create(code=PaymentMethodCodeEnum.STARS)

    def test_has_exact_supported_choices_and_global_fields(self) -> None:
        code = PaymentMethod._meta.get_field("code")

        self.assertTrue(code.unique)
        self.assertEqual(
            tuple(code.choices),
            (
                (PaymentMethodCodeEnum.PLATEGA_SBP, "СБП"),
                (PaymentMethodCodeEnum.STARS, "Telegram Stars"),
                (PaymentMethodCodeEnum.CRYPTO_PAY, "Crypto Pay"),
            ),
        )
        self.assertEqual(
            {field.name for field in PaymentMethod._meta.fields},
            {
                "id",
                "is_active",
                "created_at",
                "updated_at",
                "code",
                "commission_percent",
            },
        )
        self.assertFalse(
            any(
                field.related_model is Product
                for field in PaymentMethod._meta.get_fields()
            )
        )

    def test_commission_percent_defaults_to_zero_and_accepts_inclusive_range(self) -> None:
        PaymentMethod.objects.all().delete()
        payment_method = PaymentMethod.objects.create(
            code=PaymentMethodCodeEnum.PLATEGA_SBP
        )
        field = PaymentMethod._meta.get_field("commission_percent")

        self.assertEqual(payment_method.commission_percent, Decimal("0.00"))
        self.assertEqual(field.max_digits, 5)
        self.assertEqual(field.decimal_places, 2)
        for value in (Decimal("0.00"), Decimal("999.99")):
            with self.subTest(value=value):
                payment_method.commission_percent = value
                payment_method.full_clean()

    def test_commission_percent_rejects_values_outside_range(self) -> None:
        PaymentMethod.objects.all().delete()
        payment_method = PaymentMethod(code=PaymentMethodCodeEnum.PLATEGA_SBP)

        for value in (Decimal("-0.01"), Decimal("1000.00")):
            with self.subTest(value=value):
                payment_method.commission_percent = value
                with self.assertRaises(ValidationError):
                    payment_method.full_clean()

    def test_commission_percent_range_is_enforced_by_database(self) -> None:
        PaymentMethod.objects.all().delete()
        payment_method = PaymentMethod.objects.create(
            code=PaymentMethodCodeEnum.PLATEGA_SBP
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PaymentMethod.objects.filter(pk=payment_method.pk).update(
                    commission_percent=Decimal("-0.01")
                )
        self.assertIn(
            "payment_method_commission_percent_range",
            {constraint.name for constraint in PaymentMethod._meta.constraints},
        )
