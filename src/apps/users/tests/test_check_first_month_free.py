from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.users.tests.factories import SystemUserFactory


class TestCheckFirstMonthFree(APITestCase):
    url: str = reverse("check-first-month-free")

    def setUp(self) -> None:
        self.user = SystemUserFactory()

    def test_check_if_true(self) -> None:
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"has_access_for_free": True})

    def test_check_if_false(self) -> None:
        self.user.first_month_free_used = True
        self.user.save(update_fields=["first_month_free_used"])
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"has_access_for_free": False})

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

    def test_first_month_limit(self) -> None:
        for _ in range(50):
            SystemUserFactory(first_month_free_used=True)
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"has_access_for_free": False})
