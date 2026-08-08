import json

from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from apps.payments.enums import ProductCodeEnum
from apps.payments.models import PaymentMethod, Product
from apps.payments.tests.factories import ProductFactory


class TestGetProductView(APITestCase):
    url: str = reverse("product")

    def setUp(self) -> None:
        Product.objects.all().delete()
        PaymentMethod.objects.all().delete()
        self.platega = PaymentMethod.objects.create(code="platega_sbp")
        self.stars = PaymentMethod.objects.create(code="stars")
        self.crypto = PaymentMethod.objects.create(code="crypto_pay")
        self.mtproto_product = ProductFactory(code=ProductCodeEnum.MTPROTO_30D)
        self.vpn_provider_data = {
            "receipt": {
                "customer": {},
                "items": [
                    {
                        "description": "Оплата VPN-подписки на один месяц.",
                        "quantity": "1.00",
                        "amount": {"value": 149, "currency": "RUB"},
                        "vat_code": 4,
                        "payment_mode": "full_payment",
                    },
                ],
            }
        }
        self.vpn_product = ProductFactory(
            code=ProductCodeEnum.VPN_30D,
            title="VPN на 30 дней",
            provider_data=json.dumps(self.vpn_provider_data),
            price=14900,
            stars_price=149,
            need_email=True,
            send_email_to_provider=True,
        )

    def get_product(self, path: str) -> Response:
        return self.client.get(
            path=path,
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

    def test_get_product_view_returns_mtproto_legacy_alias(self) -> None:
        response = self.get_product(path=self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "title": self.mtproto_product.title,
                "description": self.mtproto_product.description,
                "provider_data": self.mtproto_product.provider_data_json,
                "currency": "RUB",
                "price": self.mtproto_product.price,
                "rub_amount": "0.99",
                "stars_price": self.mtproto_product.stars_price,
                "need_email": self.mtproto_product.need_email,
                "send_email_to_provider": self.mtproto_product.send_email_to_provider,
                "payment_methods": ["platega_sbp", "stars", "crypto_pay"],
            },
        )

    def test_get_product_by_code_returns_selected_active_product(self) -> None:
        response = self.get_product(
            path=reverse("product-by-code", kwargs={"code": ProductCodeEnum.VPN_30D})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["title"], self.vpn_product.title)
        self.assertEqual(response.json()["price"], float(self.vpn_product.price))
        self.assertEqual(response.json()["rub_amount"], "149.00")
        self.assertEqual(response.json()["stars_price"], self.vpn_product.stars_price)
        self.assertEqual(response.json()["provider_data"], self.vpn_provider_data)
        self.assertTrue(response.json()["need_email"])
        self.assertTrue(response.json()["send_email_to_provider"])

    def test_returns_current_payment_methods_for_both_product_routes(self) -> None:
        routes = (
            self.url,
            reverse("product-by-code", kwargs={"code": ProductCodeEnum.VPN_30D}),
        )
        states = (
            (("platega_sbp", "stars", "crypto_pay"), ["platega_sbp", "stars", "crypto_pay"]),
            (("platega_sbp", "crypto_pay"), ["platega_sbp", "crypto_pay"]),
            (("platega_sbp", "stars"), ["platega_sbp", "stars"]),
            (("platega_sbp",), ["platega_sbp"]),
            (("stars", "crypto_pay"), ["stars", "crypto_pay"]),
            (("stars",), ["stars"]),
            (("crypto_pay",), ["crypto_pay"]),
            ((), []),
        )

        for active_codes, expected in states:
            PaymentMethod.objects.all().update(is_active=False)
            PaymentMethod.objects.filter(code__in=active_codes).update(is_active=True)
            for route in routes:
                with self.subTest(route=route, active_codes=active_codes):
                    response = self.get_product(path=route)
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    self.assertEqual(response.json()["payment_methods"], expected)

    def test_returns_current_payment_methods_on_sequential_gets(self) -> None:
        first_response = self.get_product(path=self.url)
        self.assertEqual(
            first_response.json()["payment_methods"],
            ["platega_sbp", "stars", "crypto_pay"],
        )

        self.platega.is_active = False
        self.platega.save(update_fields=["is_active"])

        second_response = self.get_product(path=self.url)
        self.assertEqual(second_response.json()["payment_methods"], ["stars", "crypto_pay"])

    def test_returns_error_when_no_active_product(self) -> None:
        self.vpn_product.is_active = False
        self.vpn_product.save(update_fields=["is_active"])
        response = self.get_product(
            path=reverse("product-by-code", kwargs={"code": ProductCodeEnum.VPN_30D})
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_requires_bot_auth_token(self) -> None:
        response = self.client.get(path=self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
