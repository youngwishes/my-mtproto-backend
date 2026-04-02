from django.conf import settings
from django.urls import reverse
from rest_framework.test import APITestCase
from django.utils import timezone
from datetime import timedelta
from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory


class TestCheckAgreementView(APITestCase):
    url = reverse("user-agreement")

    def setUp(self) -> None:
        self.user = SystemUserFactory()
        self.key = MTPRotoKeyFactory(user=self.user)

    def test_http_201_true(self) -> None:
        self.assertFalse(self.user.is_agree)
        self.assertFalse(self.key.is_winner)

        response = self.client.post(
            path=self.url,
            data={"username": self.user.username, "is_agree": True},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.user.refresh_from_db()
        self.key.refresh_from_db()

        self.assertTrue(self.key.is_winner)
        self.assertTrue(self.user.is_agree)
        self.assertEqual(self.key.expired_date.date(), (timezone.now() + timedelta(days=365)).date())
        self.assertEqual(
            response.json(),
            {"link": self.key.get_proxy_link()},
        )

    def test_http_201_false(self) -> None:
        self.assertFalse(self.user.is_agree)
        self.assertFalse(self.key.is_winner)

        response = self.client.post(
            path=self.url,
            data={"username": self.user.username, "is_agree": False},
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )
        self.user.refresh_from_db()
        self.key.refresh_from_db()

        self.assertTrue(self.key.is_winner)
        self.assertFalse(self.user.is_agree)
        self.assertEqual(self.key.expired_date.date(), (timezone.now() + timedelta(days=365)).date())
        self.assertEqual(
            response.json(),
            {"link": self.key.get_proxy_link()},
        )
