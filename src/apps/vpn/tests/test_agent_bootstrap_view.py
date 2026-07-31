from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.vpn.tests.factories import VPNSubscriptionFactory


class TestAgentBootstrapView(APITestCase):
    url = reverse("vpn-agent-profiles")

    def test_returns_only_active_unexpired_profiles_to_bearer_agent(self) -> None:
        active = VPNSubscriptionFactory(expired_at=timezone.now() + timedelta(days=1))
        VPNSubscriptionFactory(is_active=False, expired_at=timezone.now() + timedelta(days=1))
        VPNSubscriptionFactory(expired_at=timezone.now() - timedelta(seconds=1))

        response = self.client.get(
            self.url,
            headers={"Authorization": f"Bearer {settings.VPN_AGENT_TOKEN}"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            [
                {
                    "access_id": active.pk,
                    "vless_uuid": str(active.vless_uuid),
                    "hysteria_secret": active.hysteria_secret,
                },
            ],
        )

    def test_rejects_request_without_agent_bearer_token(self) -> None:
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
