from __future__ import annotations

from pathlib import Path

from django.test import SimpleTestCase


class TestCryptoPayDeployArtifacts(SimpleTestCase):
    def test_backend_example_contains_crypto_settings_and_bot_has_none(self) -> None:
        root = Path(__file__).resolve().parents[4]
        backend_env = (root / ".env.example").read_text(encoding="utf-8")
        bot_config = (root / "bot/src/config.py").read_text(encoding="utf-8")

        for name in (
            "CRYPTOPAY_API_TOKEN",
            "CRYPTOPAY_BASE_URL",
            "CRYPTOPAY_WEBHOOK_SECRET",
            "CRYPTOPAY_REQUEST_TIMEOUT",
        ):
            self.assertIn(f"{name}=", backend_env)
            self.assertNotIn(name, bot_config)

    def test_compose_passes_backend_env_to_django_worker_and_beat(self) -> None:
        root = Path(__file__).resolve().parents[4]
        compose = (root / "docker-compose.yml").read_text(encoding="utf-8")

        for service in ("django", "celery-worker", "celery-beat"):
            service_block = compose.split(f"  {service}:\n", 1)[1].split("\n\n", 1)[0]
            self.assertIn("env_file:\n      - .env", service_block)

        bot_block = compose.split("  bot:\n", 1)[1].split("\n\n", 1)[0]
        self.assertNotIn("CRYPTOPAY_", bot_block)
