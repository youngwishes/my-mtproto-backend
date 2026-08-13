from __future__ import annotations

from pathlib import Path

from django.test import SimpleTestCase

from config.settings.base import ALLOWED_HOSTS


class TestPublicDomainConfiguration(SimpleTestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[4]
        self.nginx_config = (self.repo_root / "nginx" / "nginx.conf").read_text(encoding="utf-8")
        self.compose_config = (self.repo_root / "docker-compose.yml").read_text(encoding="utf-8")

    def test_django_accepts_only_transition_and_local_hosts(self) -> None:
        expected_hosts = {
            "localhost",
            "127.0.0.1",
            "django",
            "beatvault.ru",
            "dash.mtprotokeys.com",
        }

        self.assertSetEqual(set(ALLOWED_HOSTS), expected_hosts)
        self.assertEqual(len(ALLOWED_HOSTS), len(expected_hosts))

    def test_nginx_routes_approved_public_hosts_to_their_upstreams(self) -> None:
        server_names = [
            "dash.mtprotokeys.com flower.mtprotokeys.com beatvault.ru",
            "dash.mtprotokeys.com beatvault.ru",
            "flower.mtprotokeys.com",
        ]
        self.assertEqual(
            [
                line.strip().removeprefix("server_name ").removesuffix(";")
                for line in self.nginx_config.splitlines()
                if line.strip().startswith("server_name ")
            ],
            server_names,
        )

        django_https = self.nginx_config.split(
            "server_name dash.mtprotokeys.com beatvault.ru;", maxsplit=1
        )[1].split("\nserver {", maxsplit=1)[0]
        flower_https = self.nginx_config.split(
            "server_name flower.mtprotokeys.com;", maxsplit=1
        )[1].split("\nserver {", maxsplit=1)[0]
        self.assertIn("proxy_pass http://django;", django_https)
        self.assertNotIn("proxy_pass http://flower:5555;", django_https)
        self.assertIn("proxy_pass http://flower:5555;", flower_https)
        self.assertNotIn("proxy_pass http://django;", flower_https)

    def test_nginx_preserves_certificate_lineage_and_sensitive_route_redaction(self) -> None:
        certificate_path = "/etc/nginx/ssl/live/beatvault.ru/"
        self.assertEqual(self.nginx_config.count(certificate_path + "fullchain.pem"), 2)
        self.assertEqual(self.nginx_config.count(certificate_path + "privkey.pem"), 2)

        for route in (
            "location ~ ^/api/v1/vpn/subscriptions/[^/]+/$ {",
            "location ~ ^/api/v1/payments/crypto/webhooks/[^/]+/$ {",
        ):
            route_bodies = [
                section.split("\n    }", maxsplit=1)[0]
                for section in self.nginx_config.split(route)[1:]
            ]
            self.assertEqual(len(route_bodies), 2)
            self.assertTrue(all("access_log off;" in body for body in route_bodies))

    def test_flower_keeps_compose_basic_auth(self) -> None:
        self.assertIn(
            "command: celery -A config flower --port=5555 --basic_auth=${FLOWER_USER}:${FLOWER_PASSWORD}",
            self.compose_config,
        )
