from __future__ import annotations

from pathlib import Path

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APITestCase

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
