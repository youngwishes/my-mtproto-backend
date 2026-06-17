from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


@mock.patch("apps.core.decorators._log_service_error")
class TestMyServersView(APITestCase):
    url: str = reverse("my-servers")

    def setUp(self, mock_log=None) -> None:
        self.user = SystemUserFactory(username="55555555")
        self.vds1 = VDSInstanceFactory(
            name="nl1", location="🇳🇱 Нидерланды", is_active=True
        )
        self.vds2 = VDSInstanceFactory(
            name="de1", location="🇩🇪 Германия", is_active=True
        )
        self.key = MTPRotoKeyFactory(
            user=self.user,
            token="viewtoken",
            expired_date=timezone.now() + timedelta(days=30),
            is_active=True,
            was_deleted=False,
        )

    def _post(self, data: dict | None = None) -> object:
        return self.client.post(
            path=self.url,
            data=data or {"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

    def test_returns_servers_for_user_with_active_key(self, mock_log) -> None:
        response = self._post()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("expired_date", data)
        self.assertIn("servers", data)
        self.assertEqual(len(data["servers"]), 2)
        locations = [s["location"] for s in data["servers"]]
        self.assertIn("🇳🇱 Нидерланды", locations)
        self.assertIn("🇩🇪 Германия", locations)
        for server in data["servers"]:
            self.assertIn("tg://proxy", server["proxy_link"])

    def test_missing_bot_auth_token_returns_403(self, mock_log) -> None:
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_who_used_free_without_active_key_returns_error(self, mock_log) -> None:
        # Период уже израсходован, ключа нет → повторной авто-активации нет, 400.
        SystemUserFactory(username="66666666", first_month_free_used=True)
        VDSInstanceFactory(is_active=True)

        response = self._post(data={"username": "66666666"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.json())

    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_new_user_without_key_auto_activates_free_period(
        self, mock_push, mock_log
    ) -> None:
        # Новый пользователь без ключа → бесплатный период активируется, 200 + серверы.
        SystemUserFactory(username="66666666", first_month_free_used=False)

        response = self._post(data={"username": "66666666"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("expired_date", data)
        self.assertTrue(len(data["servers"]) >= 1)
        mock_push.assert_called_once()
