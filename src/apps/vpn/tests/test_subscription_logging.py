from __future__ import annotations

from pathlib import Path

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.vpn.tests.factories import VPNSubscriptionFactory


class TestVPNSubscriptionLogging(SimpleTestCase):
    def test_nginx_disables_access_log_only_for_token_subscription_route(self) -> None:
        config = (Path(__file__).resolve().parents[4] / "nginx" / "nginx.conf").read_text()
        route = "location ~ ^/api/v1/vpn/subscriptions/[^/]+/$ {"

        self.assertIn(route, config)
        route_body = config[config.index(route) :].split("\n    }", maxsplit=1)[0]
        self.assertIn("access_log off;", route_body)
        self.assertEqual(config.count("access_log off;"), 1)


class TestVPNSubscriptionApplicationLogging(APITestCase):
    def test_get_does_not_log_subscription_token_or_credentials(self) -> None:
        subscription = VPNSubscriptionFactory(
            token="private-subscription-token",
            hysteria_secret="private-hysteria-secret",
        )

        with self.assertNoLogs("config.middlewares", level="INFO"):
            response = self.client.get(f"/api/v1/vpn/subscriptions/{subscription.token}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
