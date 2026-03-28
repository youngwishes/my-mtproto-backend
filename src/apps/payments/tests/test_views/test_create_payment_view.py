from datetime import timedelta
from unittest import mock

import responses
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.payments.models import Payment
from apps.payments.tests.factories import ProductFactory
from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import MTPRotoKey
from apps.vds.tests.factories import VDSInstanceFactory


class TestCreatePaymentView(APITestCase):
    url: str = reverse("product-buy")

    def setUp(self) -> None:
        self.product = ProductFactory()
        self.vds = VDSInstanceFactory()
        self.user = SystemUserFactory()

    def _mock_vds_request(self) -> None:
        responses.add(
            method=responses.POST,
            url=self.vds.internal_url + "/api/v2/users/add",
            json={
                "tls_domain": "petrovich.ru",
                "key": "test",
                "node_number": "telemt-node01",
            },
        )

    @mock.patch("apps.core.bot.TelegramBot.send_proxy_link")
    @responses.activate
    def test_create_payment_view(self, telegram) -> None:
        self._mock_vds_request()
        response = self.client.post(
            path=self.url,
            data={
                "username": self.user.username,
                "provider_payment_charge_id": "provider_payment_charge_id",
            },
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(telegram.call_count, 1)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(MTPRotoKey.objects.count(), 1)

        key = MTPRotoKey.objects.first()
        payment = Payment.objects.first()

        self.assertEqual(payment.key, key)
        self.assertEqual(key.vds, self.vds)
        self.assertEqual(payment.user, self.user)
        self.assertEqual(
            payment.provider_payment_charge_id, "provider_payment_charge_id"
        )
        self.assertEqual(
            key.expired_date.date(), (timezone.now() + timedelta(days=30)).date()
        )

    @mock.patch("apps.core.bot.TelegramBot.send_proxy_link")
    @responses.activate
    def test_create_payment_view_twice(self, telegram) -> None:
        self._mock_vds_request()
        self.client.post(
            path=self.url,
            data={
                "username": self.user.username,
                "provider_payment_charge_id": "provider_payment_charge_id",
            },
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        payment = Payment.objects.first()
        self.assertIsNotNone(payment.key)
        self.client.post(
            path=self.url,
            data={
                "username": self.user.username,
                "provider_payment_charge_id": "provider_payment_charge_id",
            },
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        payment.refresh_from_db()
        self.assertEqual(telegram.call_count, 2)
        self.assertEqual(Payment.objects.count(), 2)
        self.assertEqual(MTPRotoKey.objects.count(), 1)
        self.assertIsNone(payment.key)
        self.assertEqual(payment.user, self.user)
        payment = Payment.objects.last()
        self.assertIsNotNone(payment.key)
        self.assertEqual(payment.user, self.user)
