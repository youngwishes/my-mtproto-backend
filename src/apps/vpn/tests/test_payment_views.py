from __future__ import annotations

from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.payments.enums import PaymentKindEnum, PaymentProviderEnum, ProductCodeEnum
from apps.payments.models import Payment
from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory
from apps.vpn.models import VPNSubscription


class TestVPNPaymentView(APITestCase):
    url = reverse("vpn-payment-buy")

    def setUp(self) -> None:
        self.user = SystemUserFactory(username="99887766")

    def _post(self, data: dict[str, str]):
        return self.client.post(
            self.url,
            data=data,
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

    def _payment_data(self, *, provider: str = PaymentProviderEnum.YUKASSA) -> dict[str, str]:
        return {
            "username": self.user.username,
            "charge_id": "charge-001",
            "provider": provider,
            "product_code": ProductCodeEnum.VPN_30D,
        }

    def test_accepts_yukassa_purchase_and_returns_external_subscription_url(self) -> None:
        response = self._post(self._payment_data())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Payment.objects.get().kind, PaymentKindEnum.VPN_SUBSCRIPTION)
        self.assertEqual(VPNSubscription.objects.count(), 1)
        self.assertIn("subscription_url", response.data)
        self.assertNotIn("testserver", response.data["subscription_url"])

    def test_accepts_stars_purchase(self) -> None:
        response = self._post(self._payment_data(provider=PaymentProviderEnum.STARS))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Payment.objects.get().provider, PaymentProviderEnum.STARS)

    def test_rejects_invalid_product_or_blank_charge_without_payment_mutation(self) -> None:
        for changed_field, value in (("product_code", "mtproto_30d"), ("charge_id", "")):
            with self.subTest(changed_field=changed_field):
                data = self._payment_data()
                data[changed_field] = value

                response = self._post(data)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(Payment.objects.count(), 0)

    def test_rejects_extra_request_fields_without_payment_mutation(self) -> None:
        data = self._payment_data()
        data["unexpected"] = "field"

        response = self._post(data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Payment.objects.count(), 0)

    def test_requires_bot_auth_token(self) -> None:
        response = self.client.post(self.url, data=self._payment_data())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_does_not_change_mtproto_key(self) -> None:
        key = MTPRotoKeyFactory(user=self.user)
        previous_expired_date = key.expired_date

        response = self._post(self._payment_data())

        key.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(key.expired_date, previous_expired_date)
