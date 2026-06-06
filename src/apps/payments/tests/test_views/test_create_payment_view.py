from datetime import timedelta
from unittest import mock

import responses
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.payments.enums import PaymentProviderEnum
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
        self.user = SystemUserFactory(username="99887766")

    def _mock_vds_request(self) -> None:
        responses.add(
            method=responses.POST,
            url=self.vds.internal_url + "/api/users",
            json={
                "tls_domain": "petrovich.ru",
                "key": "test",
            },
        )

    def _post(self, data: dict) -> object:
        return self.client.post(
            path=self.url,
            data=data,
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

    @mock.patch("apps.notifications.services.send_notification_service.send")
    @mock.patch("apps.vds.tasks.add_key_to_another_vds_instances_task.delay")
    @responses.activate
    def test_create_yukassa_payment(self, _task, telegram) -> None:
        self._mock_vds_request()
        response = self._post({
            "username": self.user.username,
            "charge_id": "yukassa_charge_001",
            "provider": PaymentProviderEnum.YUKASSA,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(telegram.call_count, 1)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(MTPRotoKey.objects.count(), 1)

        key = MTPRotoKey.objects.first()
        payment = Payment.objects.first()

        self.assertEqual(payment.key, key)
        self.assertEqual(key.vds, self.vds)
        self.assertEqual(payment.user, self.user)
        self.assertEqual(payment.charge_id, "yukassa_charge_001")
        self.assertEqual(payment.provider, PaymentProviderEnum.YUKASSA)
        self.assertEqual(
            key.expired_date.date(), (timezone.now() + timedelta(days=30)).date()
        )

    @mock.patch("apps.notifications.services.send_notification_service.send")
    @mock.patch("apps.vds.tasks.add_key_to_another_vds_instances_task.delay")
    @responses.activate
    def test_create_stars_payment(self, _task, telegram) -> None:
        self._mock_vds_request()
        response = self._post({
            "username": self.user.username,
            "charge_id": "stars_tx_789",
            "provider": PaymentProviderEnum.STARS,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(telegram.call_count, 1)

        payment = Payment.objects.first()
        self.assertEqual(payment.charge_id, "stars_tx_789")
        self.assertEqual(payment.provider, PaymentProviderEnum.STARS)

    @mock.patch("apps.notifications.services.send_notification_service.send")
    @mock.patch("apps.vds.tasks.add_key_to_another_vds_instances_task.delay")
    @responses.activate
    def test_create_payment_twice_extends_key(self, _task, telegram) -> None:
        self._mock_vds_request()
        self._post({
            "username": self.user.username,
            "charge_id": "charge_first",
            "provider": PaymentProviderEnum.YUKASSA,
        })
        payment = Payment.objects.first()
        self.assertIsNotNone(payment.key)

        self._post({
            "username": self.user.username,
            "charge_id": "charge_second",
            "provider": PaymentProviderEnum.YUKASSA,
        })
        payment.refresh_from_db()
        self.assertEqual(telegram.call_count, 2)
        self.assertEqual(Payment.objects.count(), 2)
        self.assertEqual(MTPRotoKey.objects.count(), 1)
        self.assertIsNone(payment.key)
        self.assertEqual(payment.user, self.user)
        last_payment = Payment.objects.last()
        self.assertIsNotNone(last_payment.key)
        self.assertEqual(last_payment.user, self.user)

    def test_missing_provider_returns_400(self) -> None:
        response = self._post({
            "username": self.user.username,
            "charge_id": "charge_001",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_provider_returns_400(self) -> None:
        response = self._post({
            "username": self.user.username,
            "charge_id": "charge_001",
            "provider": "paypal",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
