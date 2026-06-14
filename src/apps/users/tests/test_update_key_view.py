from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import MTPRotoKey
from apps.vds.tests.factories import MTPRotoKeyFactory


class TestUpdateKeyView(APITestCase):
    url: str = reverse("update-link")

    def setUp(self) -> None:
        self.user = SystemUserFactory()

    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_update_user_key(self, mock_push) -> None:
        user_key_before = MTPRotoKeyFactory(
            user=self.user,
            token="test1",
            expired_date=timezone.now() + timedelta(days=10),
        )
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(MTPRotoKey.objects.filter(user=self.user).count(), 1)

        user_key_after = MTPRotoKey.objects.first()
        # токен перевыпущен, запись остаётся активной
        self.assertNotEqual(user_key_after.token, "test1")
        self.assertEqual(len(user_key_after.token), 32)
        self.assertTrue(user_key_after.is_active)
        self.assertFalse(user_key_after.was_deleted)
        self.assertEqual(
            user_key_after.expired_date.date(),
            user_key_before.expired_date.date(),
        )

        # доставка — асинхронный пинок
        mock_push.assert_called_once_with(key_id=user_key_after.pk)
        self.assertEqual(
            response.json(),
            {
                "expired_date": user_key_after.expired_date.strftime("%d.%m.%y"),
            },
        )

    @mock.patch("apps.core.decorators._log_service_error")
    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_update_user_key_if_not_active(self, mock_push, service) -> None:
        user_key_before = MTPRotoKeyFactory(
            user=self.user,
            token="test1",
            expired_date=timezone.now(),
            is_active=False,
        )
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(MTPRotoKey.objects.filter(user=self.user).count(), 1)

        user_key_before.refresh_from_db()
        self.assertEqual(user_key_before.token, "test1")
        mock_push.assert_not_called()
        self.assertEqual(service.call_count, 1)

    @mock.patch("apps.core.decorators._log_service_error")
    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_update_user_key_if_was_deleted(self, mock_push, service) -> None:
        user_key_before = MTPRotoKeyFactory(
            user=self.user,
            token="test1",
            expired_date=timezone.now(),
            was_deleted=True,
        )
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(MTPRotoKey.objects.filter(user=self.user).count(), 1)

        user_key_before.refresh_from_db()
        self.assertEqual(user_key_before.token, "test1")
        mock_push.assert_not_called()
        self.assertEqual(service.call_count, 1)

    @mock.patch("apps.core.decorators._log_service_error")
    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_update_user_key_if_not_exist(self, mock_push, service) -> None:
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(MTPRotoKey.objects.filter(user=self.user).count(), 0)
        mock_push.assert_not_called()
