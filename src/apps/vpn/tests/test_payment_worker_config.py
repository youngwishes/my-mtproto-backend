from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase, override_settings


class VPNPaymentWorkerSettingsTest(SimpleTestCase):
    @override_settings()
    def test_fulfillment_task_routes_only_to_dedicated_queue(self) -> None:
        from config.settings.celery import CELERY_BEAT_SCHEDULE, CELERY_TASK_ROUTES

        self.assertEqual(
            CELERY_TASK_ROUTES["apps.vpn.apply_payment_receipt"],
            {"queue": "vpn_payment_fulfillment"},
        )
        self.assertEqual(
            CELERY_TASK_ROUTES["apps.vpn.recover_payment_receipts"],
            {"queue": "celery"},
        )
        self.assertEqual(
            CELERY_BEAT_SCHEDULE["recover-vpn-payment-receipts"]["task"],
            "apps.vpn.recover_payment_receipts",
        )


class VPNPaymentWorkerComposeTest(SimpleTestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[4]

    def test_production_compose_isolates_singleton_worker_and_shared_lock_file(
        self,
    ) -> None:
        content = (self.repo_root / "docker-compose.yml").read_text()
        singleton = re.search(
            r"^  vpn-payment-worker:\n(?P<body>(?:    .*\n|\n)+?)(?=^  \S|\Z)",
            content,
            flags=re.MULTILINE,
        )
        default = re.search(
            r"^  celery-worker:\n(?P<body>(?:    .*\n|\n)+?)(?=^  \S|\Z)",
            content,
            flags=re.MULTILINE,
        )
        self.assertIsNotNone(singleton)
        self.assertIsNotNone(default)
        singleton_body = singleton.group("body")
        default_body = default.group("body")
        self.assertIn("-Q vpn_payment_fulfillment", singleton_body)
        self.assertIn("--concurrency=1", singleton_body)
        self.assertIn("--prefetch-multiplier=1", singleton_body)
        self.assertIn("./data:/app/data", singleton_body)
        self.assertIn("VPN_PAYMENT_WRITER_LOCK_PATH: /app/data/vpn-payment-writer.lock", singleton_body)
        self.assertIn("healthcheck:", singleton_body)
        self.assertIn("check_vpn_payment_writer_lock", singleton_body)
        self.assertIn("apps.vpn.worker_entrypoint", singleton_body)
        self.assertIn("vpn-payment-worker.owner.lock", singleton_body)
        self.assertIn("-Q celery", default_body)
        self.assertNotIn("vpn_payment_fulfillment", default_body)

    def test_deploy_stops_old_singleton_before_starting_new_stack(self) -> None:
        playbook = (self.repo_root / "ansible" / "deploy.yml").read_text()
        stop_index = playbook.index("Stop previous VPN payment singleton")
        start_index = playbook.index("Deploy docker compose stack")
        self.assertLess(stop_index, start_index)
        self.assertIn("Wait for VPN payment singleton readiness", playbook)
        self.assertIn(".State.Health.Status", playbook)
        self.assertIn(".State.Health.Status == 'healthy'", playbook)
        self.assertIn("'vpn-payment-worker' in deploy_required_services", playbook)
        group_vars = (
            self.repo_root / "ansible" / "group_vars" / "mtproto_keys.yml.example"
        ).read_text()
        self.assertIn("  - vpn-payment-worker", group_vars)
