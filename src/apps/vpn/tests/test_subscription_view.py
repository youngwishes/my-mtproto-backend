from __future__ import annotations

from base64 import b64decode
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.vpn.tests.factories import VPNInstanceFactory, VPNSubscriptionFactory


class TestVPNSubscriptionView(APITestCase):
    @patch("apps.vpn.services.get_subscription_service.shuffle")
    def test_active_subscription_randomizes_node_blocks_via_default_service_wiring(
        self,
        shuffle_nodes,
    ) -> None:
        subscription = VPNSubscriptionFactory(
            vless_uuid="11111111-2222-3333-4444-555555555555",
            hysteria_secret="hysteria-secret",
        )
        first = VPNInstanceFactory(number=10, name="First", public_host="first.example.com")
        second = VPNInstanceFactory(number=20, name="Second", public_host="second.example.com")

        def reverse_nodes(instances: list[object]) -> None:
            instances.reverse()

        shuffle_nodes.side_effect = reverse_nodes

        response = self.client.get(f"/api/v1/vpn/subscriptions/{subscription.token}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["profile-title"], "mtprotokeys.com")
        self.assertEqual(
            b64decode(response.content).decode("utf-8").splitlines(),
            [
                "vless://11111111-2222-3333-4444-555555555555@second.example.com:443?"
                "encryption=none&flow=xtls-rprx-vision&security=reality&"
                "sni=www.example.com&fp=chrome&pbk=public-key&sid=short-id&type=tcp#"
                "Second%20VLESS",
                "hysteria2://hysteria-secret@second.example.com:443/?sni=www.example.com&"
                "obfs=salamander&obfs-password=obfs-password#Second%20Hysteria2",
                "vless://11111111-2222-3333-4444-555555555555@first.example.com:443?"
                "encryption=none&flow=xtls-rprx-vision&security=reality&"
                "sni=www.example.com&fp=chrome&pbk=public-key&sid=short-id&type=tcp#"
                "First%20VLESS",
                "hysteria2://hysteria-secret@first.example.com:443/?sni=www.example.com&"
                "obfs=salamander&obfs-password=obfs-password#First%20Hysteria2",
            ],
        )

    def test_active_subscription_returns_happ_profiles_without_bot_authentication(self) -> None:
        subscription = VPNSubscriptionFactory(
            vless_uuid="11111111-2222-3333-4444-555555555555",
            hysteria_secret="hysteria-secret",
        )
        instance = VPNInstanceFactory(name="Moscow", public_host="vpn.example.com")

        response = self.client.get(f"/api/v1/vpn/subscriptions/{subscription.token}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["profile-title"], "mtprotokeys.com")
        self.assertEqual(
            b64decode(response.content).decode("utf-8").splitlines(),
            [
                "vless://11111111-2222-3333-4444-555555555555@vpn.example.com:443?"
                "encryption=none&flow=xtls-rprx-vision&security=reality&"
                "sni=www.example.com&fp=chrome&pbk=public-key&sid=short-id&type=tcp#"
                "Moscow%20VLESS",
                "hysteria2://hysteria-secret@vpn.example.com:443/?sni=www.example.com&"
                "obfs=salamander&obfs-password=obfs-password#Moscow%20Hysteria2",
            ],
        )

    def test_expired_subscription_returns_empty_base64_payload(self) -> None:
        subscription = VPNSubscriptionFactory(expired_at=timezone.now() - timedelta(seconds=1))
        VPNInstanceFactory()

        response = self.client.get(f"/api/v1/vpn/subscriptions/{subscription.token}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content, b"")

    def test_inactive_subscription_returns_empty_base64_payload(self) -> None:
        subscription = VPNSubscriptionFactory(is_active=False)
        VPNInstanceFactory()

        response = self.client.get(f"/api/v1/vpn/subscriptions/{subscription.token}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content, b"")

    def test_active_subscription_without_active_instances_returns_empty_base64_payload(self) -> None:
        subscription = VPNSubscriptionFactory()

        response = self.client.get(f"/api/v1/vpn/subscriptions/{subscription.token}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content, b"")

    def test_unknown_token_returns_not_found(self) -> None:
        response = self.client.get("/api/v1/vpn/subscriptions/unknown-token/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
