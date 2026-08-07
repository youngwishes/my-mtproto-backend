from __future__ import annotations

from django.test import TestCase

from apps.payments.enums import PaymentProviderEnum, ProductCodeEnum
from apps.payments.models import PaymentMethod, Product
from apps.payments.selectors import (
    get_active_payment_method_codes,
    get_active_product_by_code,
)
from apps.payments.tests.factories import ProductFactory


class TestGetActiveProductByCode(TestCase):
    def setUp(self) -> None:
        Product.objects.all().delete()

    def test_returns_active_product_with_requested_code(self) -> None:
        product = ProductFactory(code=ProductCodeEnum.VPN_30D)
        ProductFactory(code=ProductCodeEnum.MTPROTO_30D)

        result = get_active_product_by_code(code=ProductCodeEnum.VPN_30D)

        self.assertEqual(result, product)

    def test_returns_none_for_inactive_product(self) -> None:
        ProductFactory(code=ProductCodeEnum.VPN_30D, is_active=False)

        result = get_active_product_by_code(code=ProductCodeEnum.VPN_30D)

        self.assertIsNone(result)


class TestActivePaymentMethodCodes(TestCase):
    def setUp(self) -> None:
        PaymentMethod.objects.all().delete()
        self.crypto = PaymentMethod.objects.create(
            code=PaymentProviderEnum.CRYPTO_PAY
        )
        self.stars = PaymentMethod.objects.create(code=PaymentProviderEnum.STARS)

    def test_returns_only_active_supported_codes_in_fixed_order(self) -> None:
        states = (
            (("stars", "crypto_pay"), ("stars", "crypto_pay")),
            (("stars",), ("stars",)),
            (("crypto_pay",), ("crypto_pay",)),
            ((), ()),
        )

        for active_codes, expected in states:
            with self.subTest(active_codes=active_codes):
                PaymentMethod.objects.all().update(is_active=False)
                PaymentMethod.objects.filter(code__in=active_codes).update(
                    is_active=True
                )

                self.assertEqual(get_active_payment_method_codes(), expected)

    def test_excludes_unknown_active_code(self) -> None:
        PaymentMethod.objects.create(code="unknown")

        self.assertEqual(
            get_active_payment_method_codes(), ("stars", "crypto_pay")
        )
