from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.payments.enums import ProductCodeEnum
from apps.payments.models import Product
from apps.payments.tests.factories import ProductFactory


class TestGetProductView(APITestCase):
    url: str = reverse("product")

    def setUp(self) -> None:
        Product.objects.all().delete()
        self.mtproto_product = ProductFactory(code=ProductCodeEnum.MTPROTO_30D)
        self.vpn_product = ProductFactory(code=ProductCodeEnum.VPN_30D)

    def test_get_product_view_returns_mtproto_legacy_alias(self) -> None:
        response = self.client.get(
            path=self.url,
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "title": self.mtproto_product.title,
                "description": self.mtproto_product.description,
                "provider_data": self.mtproto_product.provider_data_json,
                "currency": "RUB",
                "price": self.mtproto_product.price,
                "stars_price": self.mtproto_product.stars_price,
                "need_email": self.mtproto_product.need_email,
                "send_email_to_provider": self.mtproto_product.send_email_to_provider,
            },
        )

    def test_get_product_by_code_returns_selected_active_product(self) -> None:
        response = self.client.get(
            path=reverse("product-by-code", kwargs={"code": ProductCodeEnum.VPN_30D}),
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["title"], self.vpn_product.title)
        self.assertEqual(response.json()["price"], float(self.vpn_product.price))
        self.assertEqual(response.json()["stars_price"], self.vpn_product.stars_price)

    def test_returns_error_when_no_active_product(self) -> None:
        self.vpn_product.is_active = False
        self.vpn_product.save(update_fields=["is_active"])
        response = self.client.get(
            path=reverse("product-by-code", kwargs={"code": ProductCodeEnum.VPN_30D}),
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
