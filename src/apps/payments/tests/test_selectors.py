from __future__ import annotations

from django.test import TestCase

from apps.payments.enums import ProductCodeEnum
from apps.payments.models import Product
from apps.payments.selectors import get_active_product_by_code
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
