from __future__ import annotations

from unittest import mock

from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.exceptions import LegalTermsNotAccepted
from apps.users.models import SystemUser
from apps.users.services import get_check_first_free_link_service
from apps.users.services.dtos import CheckFirstFreeLinkIn
from apps.users.tests.factories import SystemUserFactory


class TestCheckFirstMonthFree(APITestCase):
    url: str = reverse("check-first-free-link")

    def setUp(self) -> None:
        self.user = SystemUserFactory(legal_terms_accepted=True)

    def test_first_free_month(self) -> None:
        response = self.client.post(
            path=self.url,
            data={
                "username": self.user.username,
                "telegram_username": "telegram_username",
                "invited_from_username": "",
            },
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"available_free_period": "MONTH"})

    def test_first_free_two_weeks(self) -> None:
        for _ in range(50):
            SystemUserFactory(
                first_month_free_used=True,
                legal_terms_accepted=True,
            )
        referred_user = SystemUserFactory(
            username="777001",
            invited_from_username="700001",
            legal_terms_accepted=True,
        )
        response = self.client.post(
            path=self.url,
            data={
                "username": referred_user.username,
                "telegram_username": "telegram_username",
                "invited_from_username": "ignored",
            },
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        referred_user.refresh_from_db()
        self.assertEqual(referred_user.invited_from_username, "700001")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"available_free_period": "TWO_WEEK"})

    def test_first_free_week(self) -> None:
        for _ in range(50):
            SystemUserFactory(
                first_month_free_used=True,
                legal_terms_accepted=True,
            )
        response = self.client.post(
            path=self.url,
            data={
                "username": self.user.username,
                "telegram_username": "telegram_username",
                "invited_from_username": "",
            },
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"available_free_period": "WEEK"})

    def test_check_if_false(self) -> None:
        self.user.first_month_free_used = True
        self.user.save(update_fields=["first_month_free_used"])
        response = self.client.post(
            path=self.url,
            data={
                "username": self.user.username,
                "telegram_username": "telegram_username",
                "invited_from_username": "",
            },
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"available_free_period": "NOT_AVAILABLE"})

    @mock.patch("apps.core.decorators._log_service_error")
    def test_missing_user_returns_legal_terms_error_without_write(
        self,
        _logger: mock.Mock,
    ) -> None:
        before_count = SystemUser.objects.count()

        response = self.client.post(
            path=self.url,
            data={
                "username": "777002",
                "telegram_username": "must_not_be_saved",
                "invited_from_username": "700002",
            },
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(SystemUser.objects.count(), before_count)
        self.assertFalse(SystemUser.objects.filter(username="777002").exists())

    @mock.patch("apps.core.decorators._log_service_error")
    def test_unaccepted_user_returns_legal_terms_error_without_write(
        self,
        _logger: mock.Mock,
    ) -> None:
        user = SystemUserFactory(
            username="777003",
            telegram_username="unchanged",
            invited_from_username="700003",
            legal_terms_accepted=False,
        )

        response = self.client.post(
            path=self.url,
            data={
                "username": user.username,
                "telegram_username": "replacement",
                "invited_from_username": "700004",
            },
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        user.refresh_from_db()
        self.assertFalse(user.legal_terms_accepted)
        self.assertEqual(user.telegram_username, "unchanged")
        self.assertEqual(user.invited_from_username, "700003")

    @mock.patch("apps.core.decorators._log_service_error")
    def test_service_raises_domain_error_for_missing_user(
        self,
        _logger: mock.Mock,
    ) -> None:
        service = get_check_first_free_link_service()

        with self.assertRaises(LegalTermsNotAccepted):
            service(
                data=CheckFirstFreeLinkIn(
                    username="777004",
                    telegram_username="",
                )
            )

    def test_bad_request(self) -> None:
        response = self.client.post(
            path=self.url,
            data={},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_without_token_request(self) -> None:
        response = self.client.post(
            path=self.url,
            data={},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
