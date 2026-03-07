from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.payments.tests.factories import ProductFactory


class TestGetProductView(APITestCase):
    url: str = reverse("product")

    def setUp(self) -> None:
        self.product = ProductFactory()

    def test_get_product_view(self) -> None:
        response = self.client.get(
            path=self.url,
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "title": self.product.title,
                "description": self.product.description,
                "provider_data": self.product.provider_data_json,
                "currency": "RUB",
                "price": self.product.price,
                "need_email": self.product.need_email,
                "send_email_to_provider": self.product.send_email_to_provider,
            },
        )
