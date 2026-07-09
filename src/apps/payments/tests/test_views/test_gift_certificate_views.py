from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.payments.enums import PaymentProviderEnum
from apps.payments.models import GiftCertificate, Payment
from apps.payments.tests.factories import GiftCertificateFactory
from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import MTPRotoKey


class TestGiftCertificateViews(APITestCase):
    buy_url: str = reverse("gift-certificate-buy")
    activate_url: str = reverse("gift-certificate-activate")

    def setUp(self) -> None:
        self.user = SystemUserFactory(username="99887766")

    def _post(self, url: str, data: dict) -> object:
        return self.client.post(
            path=url,
            data=data,
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

    def test_buy_returns_certificate_code(self) -> None:
        response = self._post(
            self.buy_url,
            {
                "username": self.user.username,
                "charge_id": "gift_charge_001",
                "provider": PaymentProviderEnum.YUKASSA,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertRegex(response.json()["code"], r"^KEY-[A-Z0-9]{4}-[A-Z0-9]{4}$")
        self.assertEqual(GiftCertificate.objects.count(), 1)
        self.assertEqual(Payment.objects.get().kind, Payment.Kind.GIFT_CERTIFICATE)
        self.assertEqual(MTPRotoKey.objects.count(), 0)

    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_activate_returns_expired_date(self, mock_push: mock.Mock) -> None:
        GiftCertificateFactory(code="KEY-TEST-1234")

        with self.captureOnCommitCallbacks(execute=True):
            response = self._post(
                self.activate_url,
                {"username": self.user.username, "code": "KEY-TEST-1234"},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json()["expired_date"],
            (timezone.now() + timedelta(days=30)).date().strftime("%d.%m.%y"),
        )
        key = MTPRotoKey.objects.get(user=self.user)
        mock_push.assert_called_once_with(key_id=key.pk)

    def test_activate_used_certificate_returns_400(self) -> None:
        GiftCertificateFactory(
            code="KEY-USED-1234",
            status=GiftCertificate.Status.ACTIVATED,
            activated_by=SystemUserFactory(username="111222"),
            activated_at=timezone.now(),
        )

        response = self._post(
            self.activate_url,
            {"username": self.user.username, "code": "KEY-USED-1234"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("уже активирован", response.json()["error"])
