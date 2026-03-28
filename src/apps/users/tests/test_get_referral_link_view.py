from unittest import mock

import responses
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from apps.users.tests.factories import SystemUserFactory
from apps.vds.models import MTPRotoKey
from apps.vds.tests.factories import VDSInstanceFactory


class TestGetReferralLink(TestCase):
    url: str = reverse("get-referral-link")

    def setUp(self) -> None:
        self.user = SystemUserFactory()
        self.vds = VDSInstanceFactory()

    def _mock_vds_request(self) -> None:
        responses.add(
            method=responses.POST,
            url=self.vds.internal_url + "/api/v2/users/add",
            json={
                "tls_domain": "petrovich.ru",
                "key": "test",
                "node_number": "telemt-node01",
            },
        )

    @mock.patch("apps.core.bot.TelegramBot.log_service_error")
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

    @mock.patch("apps.core.bot.TelegramBot.log_service_error")
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

    @responses.activate
    def test_get_link_with_activated_referrals(self) -> None:
        self._mock_vds_request()
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
        self.assertEqual(
            response.json(),
            {
                "link": MTPRotoKey.objects.first().get_proxy_link(),
                "expired_date": (timezone.now() + timedelta(days=14)).date().strftime("%d.%m.%y")
            },
        )

    def test_get_referral_link_with_403(self) -> None:
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
