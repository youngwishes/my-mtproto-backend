from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.payments.exceptions import AppleRedemptionRetryable
from apps.payments.models import AppleRedemption
from apps.payments.tests.factories import AppleCashbackPurchaseFactory
from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory


class TestAppleViews(APITestCase):
    status_path = "/api/v1/payments/apples/status/"
    preview_path = "/api/v1/payments/apples/redemptions/preview/"
    confirm_path = "/api/v1/payments/apples/redemptions/confirm/"

    def setUp(self) -> None:
        self.user = SystemUserFactory(username="apple-api-user", apple_balance=37)
        self.key = MTPRotoKeyFactory(
            user=self.user,
            expired_date=timezone.now() + timedelta(days=10),
        )

    def _post(self, path: str, data: dict, *, token: str | None = None):
        headers = {
            "Bot-Auth-Token": settings.BOT_AUTH_TOKEN if token is None else token
        }
        return self.client.post(path=path, data=data, headers=headers)

    def test_route_names_resolve_to_exact_apple_paths(self) -> None:
        self.assertEqual(reverse("apple-status"), self.status_path)
        self.assertEqual(reverse("apple-redemption-preview"), self.preview_path)
        self.assertEqual(reverse("apple-redemption-confirm"), self.confirm_path)

    def test_all_apple_endpoints_require_correct_bot_auth_token(self) -> None:
        requests = (
            (self.status_path, {"username": self.user.username}),
            (
                self.preview_path,
                {"username": self.user.username, "mode": "one_day"},
            ),
            (
                self.confirm_path,
                {"username": self.user.username, "confirmation_id": 1},
            ),
        )

        for path, payload in requests:
            with self.subTest(path=path, auth="missing"):
                response = self.client.post(path=path, data=payload)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
            with self.subTest(path=path, auth="wrong"):
                response = self._post(path, payload, token="wrong-token")
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_status_returns_exact_backend_derived_contract(self) -> None:
        for ordinal in range(1, 5):
            AppleCashbackPurchaseFactory(
                payment__user=self.user,
                identity_key=f"stars:apple-api-status-{ordinal}:subscription",
                eligible_purchase_count_after=ordinal,
            )

        response = self._post(
            self.status_path,
            {"username": self.user.username},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "balance": 37,
                "eligible_purchase_count": 4,
                "level": "Садовник",
                "rate_percent": 10,
                "next_level_purchase_count": 7,
                "purchases_to_next_level": 3,
                "is_max_level": False,
                "redeemable_days": 2,
                "missing_apples": 0,
                "has_existing_key": True,
            },
        )
        self.assertTrue(
            {"token", "key_id", "link", "proxy_url"}.isdisjoint(response.json())
        )

    def test_preview_returns_exact_saved_quote_without_mutation(self) -> None:
        original_expiry = self.key.expired_date

        response = self._post(
            self.preview_path,
            {"username": self.user.username, "mode": "all"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        redemption = AppleRedemption.objects.get()
        self.assertEqual(
            response.json(),
            {
                "confirmation_id": redemption.pk,
                "mode": "all",
                "apples_spent": 30,
                "days": 2,
                "projected_expired_date": (
                    original_expiry + timedelta(days=2)
                ).date().strftime("%d.%m.%y"),
            },
        )
        self.user.refresh_from_db()
        self.key.refresh_from_db()
        self.assertEqual(self.user.apple_balance, 37)
        self.assertEqual(self.key.expired_date, original_expiry)

    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_repeated_confirmation_returns_identical_saved_200_result(
        self, mock_push: mock.Mock
    ) -> None:
        preview = self._post(
            self.preview_path,
            {"username": self.user.username, "mode": "all"},
        ).json()
        payload = {
            "username": self.user.username,
            "confirmation_id": preview["confirmation_id"],
        }

        first = self._post(self.confirm_path, payload)
        second = self._post(self.confirm_path, payload)

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.json(), first.json())
        self.assertEqual(
            first.json(),
            {
                "apples_spent": 30,
                "days": 2,
                "expired_date": (
                    self.key.expired_date + timedelta(days=2)
                ).date().strftime("%d.%m.%y"),
                "balance": 7,
            },
        )
        self.user.refresh_from_db()
        self.key.refresh_from_db()
        self.assertEqual(self.user.apple_balance, 7)
        self.assertEqual(
            self.key.expired_date.date().strftime("%d.%m.%y"),
            first.json()["expired_date"],
        )
        mock_push.assert_not_called()

    def test_validation_and_eligibility_errors_return_400_without_mutation(self) -> None:
        original_expiry = self.key.expired_date
        cases = (
            (self.status_path, {"username": self.user.username, "balance": 999}),
            (
                self.preview_path,
                {
                    "username": self.user.username,
                    "mode": "custom_days",
                    "days": 99,
                },
            ),
            (
                self.confirm_path,
                {
                    "username": self.user.username,
                    "confirmation_id": 999999,
                    "key_id": self.key.pk,
                },
            ),
        )

        for path, payload in cases:
            with self.subTest(path=path):
                response = self._post(path, payload)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.user.refresh_from_db()
        self.key.refresh_from_db()
        self.assertEqual(self.user.apple_balance, 37)
        self.assertEqual(self.key.expired_date, original_expiry)
        self.assertFalse(AppleRedemption.objects.exists())

    def test_invalid_confirmation_returns_400(self) -> None:
        response = self._post(
            self.confirm_path,
            {"username": self.user.username, "confirmation_id": 999999},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_mode_returns_400_without_quote(self) -> None:
        response = self._post(
            self.preview_path,
            {"username": self.user.username, "mode": "custom_days"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(AppleRedemption.objects.exists())

    def test_preview_eligibility_errors_return_400_with_safe_detail(self) -> None:
        low_balance = SystemUserFactory(username="apple-api-low", apple_balance=14)
        MTPRotoKeyFactory(
            user=low_balance,
            expired_date=timezone.now() + timedelta(days=1),
        )
        no_key = SystemUserFactory(username="apple-api-no-key", apple_balance=15)

        insufficient = self._post(
            self.preview_path,
            {"username": low_balance.username, "mode": "one_day"},
        )
        missing_key = self._post(
            self.preview_path,
            {"username": no_key.username, "mode": "one_day"},
        )

        self.assertEqual(insufficient.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(insufficient.json()["detail"], {"missing_apples": 1})
        self.assertEqual(missing_key.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(missing_key.json()["detail"], {})
        low_balance.refresh_from_db()
        no_key.refresh_from_db()
        self.assertEqual(low_balance.apple_balance, 14)
        self.assertEqual(no_key.apple_balance, 15)
        self.assertFalse(AppleRedemption.objects.exists())

    def test_retryable_service_outcomes_return_safe_503(self) -> None:
        cases = (
            (
                "apps.payments.api.v1.views.apple_views.get_apple_status_service",
                self.status_path,
                {"username": self.user.username},
            ),
            (
                "apps.payments.api.v1.views.apple_views.get_preview_apple_redemption_service",
                self.preview_path,
                {"username": self.user.username, "mode": "one_day"},
            ),
            (
                "apps.payments.api.v1.views.apple_views.get_confirm_apple_redemption_service",
                self.confirm_path,
                {"username": self.user.username, "confirmation_id": 1},
            ),
        )

        for factory_path, path, payload in cases:
            with self.subTest(path=path), mock.patch(factory_path) as factory:
                factory.return_value.side_effect = AppleRedemptionRetryable(
                    self.user.username
                )
                response = self._post(path, payload)
                self.assertEqual(
                    response.status_code,
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                )
                self.assertEqual(
                    response.json(),
                    {
                        "error": "Не удалось завершить обмен яблок. Попробуйте ещё раз.",
                        "detail": {},
                    },
                )
