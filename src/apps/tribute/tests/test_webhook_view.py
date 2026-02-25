import os
from unittest import mock

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.tribute.models import TributeDigitalPayment
from apps.tribute.tests.factories import VDSInstanceFactory
from apps.users.models import SystemUser
from apps.vds.models import MTPRotoKey
from apps.vds.services.add_new_key import Response, VDSNotAvailable


def payload() -> dict:
    return {
        "name": "new_digital_product",
        "created_at": "2025-03-20T01:15:58.33246Z",
        "sent_at": "2025-03-20T01:15:58.542279448Z",
        "payload": {
            "product_id": 456,
            "product_name": "VPN Access - 1 Month",
            "amount": 500,
            "currency": "rub",
            "user_id": 31326,
            "telegram_user_id": 1487189460,
            "purchase_id": 78901,
            "transaction_id": 234567,
            "purchase_created_at": "2025-03-20T01:15:58.33246Z",
        },
    }


@mock.patch("apps.core.bot.TelegramBot.send_proxy_link")
class TestWebhookView(APITestCase):
    url = reverse("tribute-webhook")

    def setUp(self) -> None:
        self.vds = VDSInstanceFactory()

    def test_webhook_tribute_object(self, tgbot) -> None:
        self.assertEqual(TributeDigitalPayment.objects.count(), 0)

        with mock.patch(
            "apps.vds.services.add_new_key.AddNewKeyService.__call__",
            return_value=Response(
                key=str(os.urandom(16).hex()), tls_domain="petrovich.ru"
            ),
        ):
            response = self.client.post(self.url, data=payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(TributeDigitalPayment.objects.count(), 1)

        payment = TributeDigitalPayment.objects.get(product_id=456)
        self.assertEqual(payment.name, payload()["name"])
        self.assertEqual(payment.product_name, payload()["payload"]["product_name"])
        self.assertEqual(payment.amount, payload()["payload"]["amount"])
        self.assertEqual(payment.currency, payload()["payload"]["currency"])
        self.assertEqual(
            int(payment.telegram_user_id), payload()["payload"]["telegram_user_id"]
        )
        self.assertEqual(
            str(payment.purchase_created_at), "2025-03-20 01:15:58.332460+00:00"
        )

    def test_webhook_system_user(self, tgbot) -> None:
        self.assertEqual(SystemUser.objects.count(), 0)

        with mock.patch(
            "apps.vds.services.add_new_key.AddNewKeyService.__call__",
            return_value=Response(
                key=str(os.urandom(16).hex()), tls_domain="petrovich.ru"
            ),
        ):
            response = self.client.post(self.url, data=payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(SystemUser.objects.count(), 1)

        user = SystemUser.objects.get(username=payload()["payload"]["telegram_user_id"])
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.keys.all().count(), 1)

    def test_webhook_mtproto_key(self, tgbot) -> None:
        self.assertEqual(MTPRotoKey.objects.count(), 0)
        key = str(os.urandom(16).hex())
        with mock.patch(
            "apps.vds.services.add_new_key.AddNewKeyService.__call__",
            return_value=Response(key=key, tls_domain="petrovich.ru"),
        ):
            response = self.client.post(self.url, data=payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(MTPRotoKey.objects.count(), 1)

        mtproto_key = MTPRotoKey.objects.get(
            user__username=payload()["payload"]["telegram_user_id"]
        )
        self.assertEqual(mtproto_key.token, key)
        self.assertEqual(mtproto_key.vds, self.vds)
        self.assertEqual(
            mtproto_key.payment, TributeDigitalPayment.objects.get(product_id=456)
        )

    def test_webhook_vds_500(self, tgbot) -> None:
        self.assertEqual(MTPRotoKey.objects.count(), 0)
        self.assertEqual(SystemUser.objects.count(), 0)
        self.assertEqual(TributeDigitalPayment.objects.count(), 0)

        with self.assertRaises(VDSNotAvailable):
            response = self.client.post(self.url, data=payload(), format="json")
            self.assertEqual(
                response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        self.assertEqual(MTPRotoKey.objects.count(), 0)
        self.assertEqual(SystemUser.objects.count(), 0)
        self.assertEqual(TributeDigitalPayment.objects.count(), 0)
