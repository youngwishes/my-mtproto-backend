from __future__ import annotations

import http.client
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import time
import unittest
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
DOMAIN = "api.meow-meow-fast.site"
ORIGIN = "dash.mtprotokeys.com"
TOKEN_PATH = "/api/v1/vpn/subscriptions/test-private-token/"


def run(*args: str) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise AssertionError(f"{args[0]} failed: {result.stdout}\n{result.stderr}")
    return (result.stdout + result.stderr).strip()


class TestVPNSubscriptionProxy(unittest.TestCase):
    """Exercise the production Nginx config against an isolated TLS origin."""

    def test_subscription_proxy_contract(self) -> None:
        config = ROOT / "nginx/vpn-subscription-proxy.conf"
        self.assertTrue(config.is_file(), "Subscription proxy configuration is missing")
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            challenge_dir = directory / "webroot/.well-known/acme-challenge"
            challenge_dir.mkdir(parents=True)
            (challenge_dir / "test-challenge").write_text("acme-proof", encoding="utf-8")
            run(
                "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                "-keyout", str(directory / "key.pem"),
                "-out", str(directory / "trusted.pem"), "-days", "1",
                "-subj", f"/CN={ORIGIN}",
                "-addext", f"subjectAltName=DNS:{ORIGIN},DNS:{DOMAIN},IP:127.0.0.1",
            )
            shutil.copyfile(directory / "trusted.pem", directory / "origin.pem")
            (directory / "origin.conf").write_text(
                "server { listen 443 ssl default_server; ssl_reject_handshake on; }\n"
                f"server {{ listen 443 ssl; server_name {ORIGIN};\n"
                "ssl_certificate /certs/origin.pem; ssl_certificate_key /certs/key.pem;\n"
                f'if ($http_host != "{ORIGIN}") {{ return 421; }}\n'
                f"location = {TOKEN_PATH} {{\n"
                "default_type text/plain;\n"
                'add_header Cache-Control "private, no-store";\n'
                'add_header profile-title "mtprotokeys.com";\n'
                'add_header subscription-userinfo "expire=2000000000";\n'
                "add_header X-Upstream-Request $request_id;\n"
                'return 200 "dmxlc3M6Ly90ZXN0"; }\n'
                "location = /api/v1/vpn/subscriptions/expired/ { return 404; }\n"
                "location / { return 418; } }\n",
                encoding="utf-8",
            )
            network = f"vpn-proxy-test-{uuid4().hex[:12]}"
            origin = f"{network}-origin"
            proxy = f"{network}-proxy"
            run("docker", "network", "create", network)
            self.addCleanup(run, "docker", "network", "rm", network)
            self.addCleanup(run, "docker", "rm", "-f", origin)
            self.addCleanup(run, "docker", "rm", "-f", proxy)
            run(
                "docker", "run", "-d", "--name", origin, "--network", network,
                "--network-alias", ORIGIN,
                "-v", f"{directory}:/certs:ro",
                "-v", f"{directory / 'origin.conf'}:/etc/nginx/conf.d/default.conf:ro",
                "nginx:alpine",
            )
            run(
                "docker", "run", "-d", "--name", proxy, "--network", network,
                "-p", "127.0.0.1::443", "-p", "127.0.0.1::80",
                "-v", f"{config}:/etc/nginx/conf.d/default.conf:ro",
                "-v", f"{directory / 'trusted.pem'}:/etc/letsencrypt/live/{DOMAIN}/fullchain.pem:ro",
                "-v", f"{directory / 'key.pem'}:/etc/letsencrypt/live/{DOMAIN}/privkey.pem:ro",
                "-v", f"{directory / 'trusted.pem'}:/etc/ssl/certs/ca-certificates.crt:ro",
                "-v", f"{directory / 'webroot'}:/var/www/certbot:ro",
                "nginx:alpine",
            )
            tls_port = int(run("docker", "port", proxy, "443/tcp").rsplit(":", 1)[1])
            http_port = int(run("docker", "port", proxy, "80/tcp").rsplit(":", 1)[1])
            context = ssl.create_default_context(cafile=str(directory / "trusted.pem"))

            def request(path: str, *, method: str = "GET", tls: bool = True):
                connection = (
                    http.client.HTTPSConnection("127.0.0.1", tls_port, context=context, timeout=10)
                    if tls else http.client.HTTPConnection("127.0.0.1", http_port, timeout=10)
                )
                try:
                    connection.request(method, path, headers={"Host": DOMAIN})
                    response = connection.getresponse()
                    return response.status, dict(response.getheaders()), response.read()
                finally:
                    connection.close()

            for attempt in range(50):
                try:
                    request("/")
                    break
                except (OSError, http.client.HTTPException):
                    if attempt == 49:
                        self.fail(run("docker", "logs", proxy))
                    time.sleep(0.1)

            with self.subTest("preserves body, metadata, path and upstream Host/SNI"):
                status, headers, body = request(TOKEN_PATH)
                self.assertEqual(status, 200)
                self.assertEqual(body, b"dmxlc3M6Ly90ZXN0")
                self.assertEqual(headers["Content-Type"], "text/plain")
                self.assertEqual(headers["profile-title"], "mtprotokeys.com")
                self.assertEqual(headers["subscription-userinfo"], "expire=2000000000")
                self.assertEqual(headers["Cache-Control"], "private, no-store")
                self.assertNotIn("Location", headers)
                first_request = headers["X-Upstream-Request"]
                self.assertNotEqual(request(TOKEN_PATH)[1]["X-Upstream-Request"], first_request)

            with self.subTest("preserves revoked or expired subscription status"):
                self.assertEqual(request("/api/v1/vpn/subscriptions/expired/")[0], 404)

            with self.subTest("exposes only subscription reads"):
                for path in ("/", "/admin/", "/api/v1/vpn/menu/", "/api/v1/vpn/reissue/"):
                    self.assertEqual(request(path)[0], 404, path)
                for method in ("POST", "PUT", "DELETE", "PATCH"):
                    self.assertEqual(request(TOKEN_PATH, method=method)[0], 403, method)

            with self.subTest("redirects HTTP to the public HTTPS domain"):
                status, headers, _ = request(TOKEN_PATH, tls=False)
                self.assertEqual(status, 301)
                self.assertEqual(headers["Location"], f"https://{DOMAIN}{TOKEN_PATH}")

            with self.subTest("serves certificate renewal challenges over HTTP"):
                status, _, body = request("/.well-known/acme-challenge/test-challenge", tls=False)
                self.assertEqual(status, 200)
                self.assertEqual(body, b"acme-proof")

            with self.subTest("rejects an untrusted upstream certificate"):
                run(
                    "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                    "-keyout", str(directory / "key.pem"),
                    "-out", str(directory / "origin.pem"), "-days", "1",
                    "-subj", f"/CN={ORIGIN}", "-addext", f"subjectAltName=DNS:{ORIGIN}",
                )
                run("docker", "restart", origin)
                # Prove the origin is serving before testing certificate rejection:
                # an ordinary startup connection failure must not satisfy this check.
                for attempt in range(50):
                    try:
                        body = run(
                            "docker", "exec", origin, "wget", "--no-check-certificate",
                            "-q", "-O", "-", f"https://{ORIGIN}{TOKEN_PATH}",
                        )
                        self.assertEqual(body, "dmxlc3M6Ly90ZXN0")
                        break
                    except AssertionError:
                        if attempt == 49:
                            raise
                        time.sleep(0.1)
                self.assertEqual(request(TOKEN_PATH)[0], 502)

            with self.subTest("does not log subscription tokens even on upstream failure"):
                self.assertNotIn("test-private-token", run("docker", "logs", proxy))


if __name__ == "__main__":
    unittest.main()
