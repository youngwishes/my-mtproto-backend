from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import MTPRotoKey
from apps.vds.tests.factories import MTPRotoKeyFactory


class TestGetReferralLink(TestCase):
    url: str = reverse("get-referral-link")

    def setUp(self) -> None:
        self.user = SystemUserFactory()

    @mock.patch("apps.core.decorators._log_service_error")
    def test_get_link_without_referrals(self, log) -> None:
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {
                "detail": {},
                "error": "🔒 Пригласите как минимум 5 пользователей. Используйте для этого вашу реферальную ссылку. Каждый приглашенный пользователь должен воспользоваться бесплатным периодом в 14 дней по вашей реферальной ссылке.",
            },
        )

    @mock.patch("apps.core.decorators._log_service_error")
    def test_get_link_with_non_activated_referrals(self, log) -> None:
        for _ in range(5):
            SystemUserFactory(
                invited_from_username=self.user.username,
            )
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {
                "detail": {},
                "error": "🔒 Пригласите как минимум 5 пользователей. Используйте для этого вашу реферальную ссылку. Каждый приглашенный пользователь должен воспользоваться бесплатным периодом в 14 дней по вашей реферальной ссылке.",
            },
        )

    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_get_link_with_activated_referrals(self, mock_push) -> None:
        for _ in range(5):
            SystemUserFactory(
                invited_from_username=self.user.username,
                referral_activated=True,
            )
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_push.assert_called_once_with(key_id=MTPRotoKey.objects.first().pk)
        self.assertEqual(
            response.json(),
            {
                "expired_date": (timezone.now() + timedelta(days=14)).date().strftime("%d.%m.%y")
            },
        )

    @mock.patch("apps.vds.tasks.push_key_to_servers_task.delay")
    def test_reward_extends_active_key_by_14_days(self, mock_push) -> None:
        # У пользователя есть активная подписка → награда ПРОДЛЕВАЕТ её на 14 дней,
        # а не затирает (тот же ключ/token, время не теряется).
        for _ in range(5):
            SystemUserFactory(
                invited_from_username=self.user.username,
                referral_activated=True,
            )
        key = MTPRotoKeyFactory(
            user=self.user,
            expired_date=timezone.now() + timedelta(days=20),
            was_deleted=False,
        )
        original_token = str(key.token)
        original_expiry = key.expired_date

        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # ключ не пересоздан
        self.assertEqual(MTPRotoKey.objects.count(), 1)
        key.refresh_from_db()
        self.assertEqual(str(key.token), original_token)
        self.assertAlmostEqual(
            key.expired_date,
            original_expiry + timedelta(days=14),
            delta=timedelta(seconds=5),
        )
        # продление — чистый DB, секрет на VDS не меняется → пуш не нужен
        mock_push.assert_not_called()
        self.user.refresh_from_db()
        self.assertEqual(self.user.referral_link_activated_count, 1)
        self.assertEqual(
            response.json(),
            {"expired_date": key.expired_date.date().strftime("%d.%m.%y")},
        )

    def test_get_referral_link_with_403(self) -> None:
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
