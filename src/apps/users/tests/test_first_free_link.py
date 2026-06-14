from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.utils import timezone
from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import MTPRotoKey


class TestFirstFreeLink(APITestCase):
    url: str = reverse("first-free-link")

    def setUp(self) -> None:
        self.user = SystemUserFactory()

    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_first_free_link_30days(self, mock_push) -> None:
        self.assertFalse(self.user.first_month_free_used)
        self.assertEqual(MTPRotoKey.objects.count(), 0)
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(MTPRotoKey.objects.count(), 1)
        self.user.refresh_from_db()
        self.assertTrue(self.user.first_month_free_used)
        self.assertFalse(self.user.referral_activated)
        # выдача — чистая запись в БД, сервер не выбирается
        self.assertEqual(
            MTPRotoKey.objects.first().expired_date.date(),
            (timezone.now() + timedelta(days=30)).date(),
        )

        # доставка — асинхронный пинок, синхронных HTTP нет
        mock_push.assert_called_once_with(key_id=MTPRotoKey.objects.first().pk)
        self.assertEqual(
            response.json(),
            {
                "expired_date": (timezone.now() + timedelta(days=30))
                .date()
                .strftime("%d.%m.%y"),
            },
        )

    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_first_free_link_7days(self, mock_push) -> None:
        for _ in range(50):
            SystemUserFactory(first_month_free_used=True)
        self.assertFalse(self.user.first_month_free_used)
        self.assertEqual(MTPRotoKey.objects.count(), 0)
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(MTPRotoKey.objects.count(), 1)
        self.user.refresh_from_db()
        self.assertTrue(self.user.first_month_free_used)
        self.assertFalse(self.user.referral_activated)
        self.assertEqual(
            MTPRotoKey.objects.first().expired_date.date(),
            (timezone.now() + timedelta(days=7)).date(),
        )
        mock_push.assert_called_once_with(key_id=MTPRotoKey.objects.first().pk)
        self.assertEqual(
            response.json(),
            {
                "expired_date": (timezone.now() + timedelta(days=7))
                .date()
                .strftime("%d.%m.%y"),
            },
        )

    @mock.patch("apps.core.decorators._log_service_error")
    def test_first_free_link_duplicate(self, service) -> None:
        self.user.first_month_free_used = True
        self.user.save(update_fields=["first_month_free_used"])

        self.assertEqual(MTPRotoKey.objects.count(), 0)
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(MTPRotoKey.objects.count(), 0)
        self.user.refresh_from_db()
        self.assertTrue(self.user.first_month_free_used)
        self.assertEqual(service.call_count, 1)

    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_first_free_link_with_referral_14days(self, mock_push) -> None:
        self.assertEqual(MTPRotoKey.objects.count(), 0)
        self.user.invited_from_username = "test"
        self.user.save()
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(MTPRotoKey.objects.count(), 1)
        self.user.refresh_from_db()
        self.assertTrue(self.user.first_month_free_used)
        self.assertTrue(self.user.referral_activated)
        self.assertEqual(
            MTPRotoKey.objects.first().expired_date.date(),
            (timezone.now() + timedelta(days=14)).date(),
        )

        mock_push.assert_called_once_with(key_id=MTPRotoKey.objects.first().pk)
        self.assertEqual(
            response.json(),
            {
                "expired_date": (timezone.now() + timedelta(days=14))
                .date()
                .strftime("%d.%m.%y"),
            },
        )


    def test_first_free_link_403(self) -> None:
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_first_free_link_400(self) -> None:
        response = self.client.post(
            path=self.url,
            data={},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
