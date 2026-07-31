from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.tests.factories import SystemUserFactory
from apps.vpn.tests.factories import VPNSubscriptionFactory


class TestVPNMenuView(APITestCase):
    def test_active_subscription_returns_exact_menu_payload(self) -> None:
        user = SystemUserFactory(username="12345678")
        subscription = VPNSubscriptionFactory(user=user)

        response = self.client.get(
            f"/api/v1/vpn/menu/?username={user.username}",
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "status": "active",
                "expired_at": subscription.expired_at.isoformat().replace("+00:00", "Z"),
                "subscription_url": (
                    f"{settings.VPN_SUBSCRIPTION_BASE_URL.rstrip('/')}"
                    f"/api/v1/vpn/subscriptions/{subscription.token}/"
                ),
            },
        )

    def test_user_without_subscription_returns_none_payload(self) -> None:
        user = SystemUserFactory(username="87654321")

        response = self.client.get(
            f"/api/v1/vpn/menu/?username={user.username}",
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {"status": "none", "expired_at": None, "subscription_url": None},
        )

    def test_expired_subscription_returns_stable_url_with_expired_status(self) -> None:
        user = SystemUserFactory(username="99999999")
        subscription = VPNSubscriptionFactory(
            user=user,
            expired_at=timezone.now() - timedelta(seconds=1),
        )

        response = self.client.get(
            f"/api/v1/vpn/menu/?username={user.username}",
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "status": "expired",
                "expired_at": subscription.expired_at.isoformat().replace("+00:00", "Z"),
                "subscription_url": (
                    f"{settings.VPN_SUBSCRIPTION_BASE_URL.rstrip('/')}"
                    f"/api/v1/vpn/subscriptions/{subscription.token}/"
                ),
            },
        )

    def test_inactive_subscription_returns_expired_status(self) -> None:
        user = SystemUserFactory(username="00000000")
        subscription = VPNSubscriptionFactory(user=user, is_active=False)

        response = self.client.get(
            f"/api/v1/vpn/menu/?username={user.username}",
            headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "expired")
        self.assertEqual(
            response.json()["subscription_url"],
            (
                f"{settings.VPN_SUBSCRIPTION_BASE_URL.rstrip('/')}"
                f"/api/v1/vpn/subscriptions/{subscription.token}/"
            ),
        )

    def test_requires_bot_authentication(self) -> None:
        response = self.client.get("/api/v1/vpn/menu/?username=12345678")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
