from __future__ import annotations

from pathlib import Path

from django.test import SimpleTestCase


class VPNSubscriptionNginxConfigTest(SimpleTestCase):
    def test_safe_static_route_telemetry_and_xff_overwrite(self) -> None:
        config = (Path(__file__).resolve().parents[4] / "nginx/nginx.conf").read_text()
        locations = config.split("location ^~ /api/v1/vpn/subscriptions/ {")[1:]
        self.assertEqual(len(locations), 2)
        for raw_location in locations:
            location = raw_location.split("}", 1)[0]
            self.assertIn("access_log /dev/stdout vpn_subscription", location)
            self.assertNotIn("access_log off", location)
            self.assertIn("proxy_set_header X-Forwarded-For $remote_addr", location)
        http_location = locations[0].split("}", 1)[0]
        https_location = locations[1].split("}", 1)[0]
        self.assertIn("return 308 https://$host$request_uri", http_location)
        self.assertNotIn("proxy_pass", http_location)
        self.assertIn("proxy_pass http://django", https_location)
        log_format = config.split("log_format vpn_subscription", 1)[1].split(";", 1)[0]
        self.assertIn("vpn_subscription", log_format)
        self.assertIn("$status", log_format)
        self.assertIn("$request_time", log_format)
        self.assertNotIn("$request_uri", log_format)
        self.assertNotIn("$args", log_format)
