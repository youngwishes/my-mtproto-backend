from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.payments.enums import PaymentKindEnum, PaymentProviderEnum, ProductCodeEnum
from apps.payments.models import AppleCashbackPurchase, GiftCertificate, Payment
from apps.payments.tests.factories import (
    AppleCashbackPurchaseFactory,
    GiftCertificateFactory,
    PaymentFactory,
    ProductFactory,
)
from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import MTPRotoKey


class TestGiftCertificateViews(APITestCase):
    buy_url: str = reverse("gift-certificate-buy")
    activate_url: str = reverse("gift-certificate-activate")

    def setUp(self) -> None:
        self.user = SystemUserFactory(username="99887766")
        ProductFactory(
            code=ProductCodeEnum.MTPROTO_30D,
            price=9900,
            currency="RUB",
        )

    def _post(self, url: str, data: dict) -> object:
        return self.client.post(
            path=url,
            data=data,
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

    def test_buy_requires_correct_bot_auth_token(self) -> None:
        payload = {
            "username": self.user.username,
            "charge_id": "auth-gift",
            "provider": PaymentProviderEnum.YUKASSA,
        }

        missing = self.client.post(path=self.buy_url, data=payload)
        wrong = self.client.post(
            path=self.buy_url,
            data=payload,
            headers={"Bot-Auth-Token": "wrong-token"},
        )

        self.assertEqual(missing.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(wrong.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Payment.objects.exists())

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
        self.assertEqual(set(response.json()), {"code", "loyalty"})
        self.assertRegex(response.json()["code"], r"^KEY-[A-Z0-9]{4}-[A-Z0-9]{4}$")
        self.assertEqual(
            response.json()["loyalty"],
            {
                "apples_earned": 5,
                "rate_percent": 5,
                "balance": 5,
                "eligible_purchase_count": 1,
                "level": "Новичок",
                "level_up": False,
                "next_purchase_rate_percent": 5,
            },
        )
        self.assertEqual(GiftCertificate.objects.count(), 1)
        self.assertEqual(Payment.objects.get().kind, Payment.Kind.GIFT_CERTIFICATE)
        self.assertEqual(MTPRotoKey.objects.count(), 0)

    def test_buy_duplicate_returns_unchanged_code_and_loyalty(self) -> None:
        request = {
            "username": self.user.username,
            "charge_id": "gift-api-duplicate",
            "provider": PaymentProviderEnum.YUKASSA,
        }

        first = self._post(self.buy_url, request)
        second = self._post(self.buy_url, request)

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.json(), first.json())
        self.assertEqual(set(second.json()), {"code", "loyalty"})
        self.assertEqual(GiftCertificate.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(AppleCashbackPurchase.objects.count(), 1)

    def test_buy_historical_replay_returns_exact_tag_without_mutation(self) -> None:
        payment = PaymentFactory(
            user=self.user,
            provider=PaymentProviderEnum.YUKASSA,
            charge_id="historical-api-gift",
            kind=PaymentKindEnum.GIFT_CERTIFICATE,
        )
        AppleCashbackPurchaseFactory(
            payment=payment,
            identity_key="yukassa:historical-api-gift:gift_certificate",
            rate_percent=None,
            apples_earned=0,
            balance_after=0,
            eligible_purchase_count_after=1,
            result_expired_at=None,
        )

        response = self._post(
            self.buy_url,
            {
                "username": self.user.username,
                "charge_id": "historical-api-gift",
                "provider": PaymentProviderEnum.YUKASSA,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"kind": "historical_replay"})
        self.assertEqual(set(response.json()), {"kind"})
        self.user.refresh_from_db()
        self.assertEqual(self.user.apple_balance, 0)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(AppleCashbackPurchase.objects.count(), 1)
        self.assertFalse(GiftCertificate.objects.exists())

    def test_buy_rejects_blank_charge_id_without_effect(self) -> None:
        response = self._post(
            self.buy_url,
            {
                "username": self.user.username,
                "charge_id": "   ",
                "provider": PaymentProviderEnum.YUKASSA,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Payment.objects.exists())

    def test_buy_rejects_client_supplied_rate(self) -> None:
        response = self._post(
            self.buy_url,
            {
                "username": self.user.username,
                "charge_id": "gift-authoritative-rate",
                "provider": PaymentProviderEnum.YUKASSA,
                "rate_percent": 99,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Payment.objects.exists())

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
