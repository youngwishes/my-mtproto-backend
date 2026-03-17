from unittest import mock

from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import SystemUser
from apps.users.tests.factories import SystemUserFactory


class TestCheckFirstMonthFree(APITestCase):
    url: str = reverse("check-first-free-link")

    def setUp(self) -> None:
        self.user = SystemUserFactory()

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
            SystemUserFactory(first_month_free_used=True)
        response = self.client.post(
            path=self.url,
            data={
                "username": "new_user",
                "telegram_username": "telegram_username",
                "invited_from_username": "user",
            },
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        user = SystemUser.objects.get(username="new_user")
        self.assertEqual(user.invited_from_username, "user")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"available_free_period": "TWO_WEEK"})

    def test_first_free_week(self) -> None:
        for _ in range(50):
            SystemUserFactory(first_month_free_used=True)
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

    @mock.patch("apps.core.bot.TelegramBot.log_bad_request")
    def test_bad_request(self, notify_bad_request) -> None:
        response = self.client.post(
            path=self.url,
            data={},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(notify_bad_request.call_count, 1)

    def test_without_token_request(self) -> None:
        response = self.client.post(
            path=self.url,
            data={},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
