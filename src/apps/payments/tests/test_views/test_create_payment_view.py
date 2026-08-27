from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.payments.enums import PaymentKindEnum, PaymentProviderEnum, ProductCodeEnum
from apps.payments.models import AppleCashbackPurchase, Payment
from apps.payments.tests.factories import (
    AppleCashbackPurchaseFactory,
    PaymentFactory,
    ProductFactory,
)
from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import MTPRotoKey


class TestCreatePaymentView(APITestCase):
    url: str = reverse("product-buy")

    def setUp(self) -> None:
        self.product = ProductFactory(
            code=ProductCodeEnum.MTPROTO_30D,
            price=9900,
            currency="RUB",
        )
        self.user = SystemUserFactory(username="99887766")

    def _post(self, data: dict) -> object:
        return self.client.post(
            path=self.url,
            data=data,
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

    def test_create_payment_requires_correct_bot_auth_token(self) -> None:
        payload = {
            "username": self.user.username,
            "charge_id": "auth-subscription",
            "provider": PaymentProviderEnum.STARS,
        }

        missing = self.client.post(path=self.url, data=payload)
        wrong = self.client.post(
            path=self.url,
            data=payload,
            headers={"Bot-Auth-Token": "wrong-token"},
        )

        self.assertEqual(missing.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(wrong.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Payment.objects.exists())

    @mock.patch("apps.notifications.services.send_notification_service.send_telegram_message")
    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_create_stars_payment_issues_key_and_loyalty(self, mock_push, telegram) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            response = self._post({
                "username": self.user.username,
                "charge_id": "stars_charge_001",
                "provider": PaymentProviderEnum.STARS,
            })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "expired_date": (timezone.now() + timedelta(days=30))
                .date()
                .strftime("%d.%m.%y"),
                "loyalty": {
                    "apples_earned": 5,
                    "rate_percent": 5,
                    "balance": 5,
                    "eligible_purchase_count": 1,
                    "level": "Новичок",
                    "level_up": False,
                    "next_purchase_rate_percent": 5,
                },
            },
        )
        self.assertEqual(telegram.call_count, 0)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(MTPRotoKey.objects.count(), 1)

        key = MTPRotoKey.objects.first()
        payment = Payment.objects.first()

        self.assertEqual(payment.key, key)
        mock_push.assert_called_once_with(key_id=key.pk)
        self.assertEqual(payment.user, self.user)
        self.assertEqual(payment.charge_id, "stars_charge_001")
        self.assertEqual(payment.provider, PaymentProviderEnum.STARS)
        self.assertEqual(
            key.expired_date.date(), (timezone.now() + timedelta(days=30)).date()
        )

    @mock.patch("apps.notifications.services.send_notification_service.send_telegram_message")
    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_create_stars_payment_saves_provider(self, mock_push, telegram) -> None:
        response = self._post({
            "username": self.user.username,
            "charge_id": "stars_tx_789",
            "provider": PaymentProviderEnum.STARS,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["loyalty"]["apples_earned"], 5)
        self.assertEqual(telegram.call_count, 0)

        payment = Payment.objects.first()
        self.assertEqual(payment.charge_id, "stars_tx_789")
        self.assertEqual(payment.provider, PaymentProviderEnum.STARS)

    @mock.patch("apps.notifications.services.send_notification_service.send_telegram_message")
    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_create_payment_twice_extends_key(self, mock_push, telegram) -> None:
        first_response = self._post({
            "username": self.user.username,
            "charge_id": "charge_first",
            "provider": PaymentProviderEnum.STARS,
        })
        payment = Payment.objects.first()
        self.assertIsNotNone(payment.key)

        second_response = self._post({
            "username": self.user.username,
            "charge_id": "charge_second",
            "provider": PaymentProviderEnum.STARS,
        })
        payment.refresh_from_db()
        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.json()["loyalty"]["balance"], 10)
        self.assertEqual(telegram.call_count, 0)
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

    def test_blank_charge_id_returns_400_without_effect(self) -> None:
        response = self._post({
            "username": self.user.username,
            "charge_id": "   ",
            "provider": PaymentProviderEnum.STARS,
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Payment.objects.exists())

    def test_backend_authoritative_purchase_rejects_price_input(self) -> None:
        response = self._post({
            "username": self.user.username,
            "charge_id": "authoritative-price",
            "provider": PaymentProviderEnum.STARS,
            "price": 1,
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Payment.objects.exists())

    def test_historical_replay_returns_exact_tag_without_mutation(self) -> None:
        payment = PaymentFactory(
            user=self.user,
            provider=PaymentProviderEnum.STARS,
            charge_id="historical-api-subscription",
            kind=PaymentKindEnum.SUBSCRIPTION,
        )
        AppleCashbackPurchaseFactory(
            payment=payment,
            identity_key="stars:historical-api-subscription:subscription",
            rate_percent=None,
            apples_earned=0,
            balance_after=0,
            eligible_purchase_count_after=1,
            result_expired_at=None,
        )

        response = self._post({
            "username": self.user.username,
            "charge_id": "historical-api-subscription",
            "provider": PaymentProviderEnum.STARS,
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"kind": "historical_replay"})
        self.assertEqual(set(response.json()), {"kind"})
        self.user.refresh_from_db()
        self.assertEqual(self.user.apple_balance, 0)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(AppleCashbackPurchase.objects.count(), 1)
        self.assertFalse(MTPRotoKey.objects.exists())

    def test_post_launch_duplicate_returns_unchanged_full_response(self) -> None:
        request = {
            "username": self.user.username,
            "charge_id": "post-launch-api-subscription",
            "provider": PaymentProviderEnum.STARS,
        }

        first = self._post(request)
        second = self._post(request)

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.json(), first.json())
        self.assertEqual(set(second.json()), {"expired_date", "loyalty"})
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(AppleCashbackPurchase.objects.count(), 1)
