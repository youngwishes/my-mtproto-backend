from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from apps.users.tests.factories import SystemUserFactory


class TestReferralCabinet(TestCase):
    url: str = reverse("referral-cabinet")

    def setUp(self) -> None:
        self.user = SystemUserFactory()

    def test_referral_cabinet_without_data(self) -> None:
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

        self.assertEqual(
            response.json(),
            {
                "total_referrals_count": 0,
                "active_referrals_count": 0,
                "referral_link": self.user.referral_link,
                "link_activated_count": 0,
            },
        )

    def test_referral_cabinet_with_data(self) -> None:
        SystemUserFactory(invited_from_username=self.user.username)
        SystemUserFactory(invited_from_username=self.user.username)
        SystemUserFactory(invited_from_username=self.user.username, referral_activated=True)

        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

        self.assertEqual(
            response.json(),
            {
                "total_referrals_count": 3,
                "active_referrals_count": 1,
                "referral_link": self.user.referral_link,
                "link_activated_count": 0,
            },
        )

    def test_referral_cabinet_with_403(self) -> None:
        response = self.client.post(
            path=self.url,
            data={"username": self.user.username},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
