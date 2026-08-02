from __future__ import annotations

from django.conf import settings
from django.test import SimpleTestCase


class TestCryptoReconciliationSchedule(SimpleTestCase):
    def test_reconciliation_runs_every_ten_minutes(self) -> None:
        entry = settings.CELERY_BEAT_SCHEDULE["reconcile-crypto-payments"]

        self.assertEqual(
            entry["task"],
            "apps.payments.tasks.reconcile_crypto_payments_task",
        )
        self.assertEqual(entry["schedule"]._orig_minute, "*/10")
