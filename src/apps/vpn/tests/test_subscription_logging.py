from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.vpn.services.dtos import VPNReissueOut
from apps.vpn.tests.factories import VPNSubscriptionFactory


class TestVPNSubscriptionLogging(SimpleTestCase):
    def test_nginx_disables_access_log_for_http_and_https_subscription_routes(self) -> None:
        config = (Path(__file__).resolve().parents[4] / "nginx" / "nginx.conf").read_text()
        route = "location ~ ^/api/v1/vpn/subscriptions/[^/]+/$ {"

        route_bodies = [
            section.split("\n    }", maxsplit=1)[0]
            for section in config.split(route)[1:]
        ]
        self.assertEqual(len(route_bodies), 2)
        self.assertIn("access_log off;", route_bodies[0])
        self.assertIn("return 301 https://$host$request_uri;", route_bodies[0])
        self.assertIn("access_log off;", route_bodies[1])
        self.assertIn("proxy_pass http://django;", route_bodies[1])


class TestVPNSubscriptionApplicationLogging(APITestCase):
    @override_settings(BOT_AUTH_TOKEN="private-bot-auth-token")
    @patch("apps.vpn.api.v1.views.reissue_views.get_reissue_vpn_subscription_service")
    def test_reissue_request_log_does_not_include_credentials_or_bot_token(
        self,
        get_reissue_service: Mock,
    ) -> None:
        """Catches logging that serializes reissue request credentials or bot auth."""
        subscription = VPNSubscriptionFactory(
            token="old-private-subscription-token",
            vless_uuid="11111111-2222-3333-4444-555555555555",
            hysteria_secret="old-private-hysteria-secret",
        )
        get_reissue_service.return_value.return_value = VPNReissueOut(
            expired_at=subscription.expired_at,
            subscription_url="https://dash.example.com/api/v1/vpn/subscriptions/new-private-token/",
        )

        with self.assertLogs("config.middlewares", level="INFO") as captured_logs:
            response = self.client.post(
                "/api/v1/vpn/reissue/",
                data={"username": subscription.user.username},
                headers={"Bot-Auth-Token": settings.BOT_AUTH_TOKEN},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        text = "\n".join(captured_logs.output)
        self.assertEqual(
            text,
            "INFO:config.middlewares:{'method': 'POST', 'path': '/api/v1/vpn/reissue/'}",
        )
        for private_value in (
            subscription.token,
            str(subscription.vless_uuid),
            subscription.hysteria_secret,
            "new-private-token",
            settings.BOT_AUTH_TOKEN,
        ):
            self.assertNotIn(private_value, text)

    def test_get_does_not_log_subscription_token_or_credentials(self) -> None:
        subscription = VPNSubscriptionFactory(
            token="private-subscription-token",
            hysteria_secret="private-hysteria-secret",
        )

        with (
            self.assertNoLogs("config.middlewares", level="INFO"),
            self.assertNoLogs("django.request", level="WARNING"),
        ):
            response = self.client.get(f"/api/v1/vpn/subscriptions/{subscription.token}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unknown_subscription_warning_redacts_token(self) -> None:
        token = "unknown-private-subscription-token"

        with self.assertLogs("django.request", level="WARNING") as captured_logs:
            response = self.client.get(f"/api/v1/vpn/subscriptions/{token}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertNotIn(token, "\n".join(captured_logs.output))
        self.assertIn(
            "/api/v1/vpn/subscriptions/[REDACTED]/",
            "\n".join(captured_logs.output),
        )
