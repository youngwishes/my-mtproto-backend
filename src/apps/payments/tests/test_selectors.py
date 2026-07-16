from __future__ import annotations

from django.test import TestCase

from apps.payments.enums import ProductCodeEnum
from apps.payments.selectors import get_active_product_by_code
from apps.payments.tests.factories import ProductFactory


class ProductSelectorsTest(TestCase):
    def test_returns_only_active_product_with_exact_stable_code(self) -> None:
        expected = ProductFactory(code=ProductCodeEnum.MTPROTO_30D)
        ProductFactory(code=ProductCodeEnum.VLESS_30D, is_active=False)

        result = get_active_product_by_code(code=ProductCodeEnum.MTPROTO_30D)

        self.assertEqual(result, expected)

    def test_does_not_fall_back_to_another_product(self) -> None:
        ProductFactory(code=ProductCodeEnum.MTPROTO_30D)

        result = get_active_product_by_code(code=ProductCodeEnum.VLESS_30D)

        self.assertIsNone(result)

