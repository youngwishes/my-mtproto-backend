from __future__ import annotations

from unittest import mock

from django.test import SimpleTestCase

from apps.payments.tasks import reconcile_crypto_payments_task


class TestReconcileCryptoPaymentsTask(SimpleTestCase):
    @mock.patch("apps.payments.tasks.get_reconcile_crypto_payments_service")
    @mock.patch("apps.payments.tasks.logger")
    def test_delegates_to_service_and_logs_exact_counters(
        self,
        logger: mock.Mock,
        get_service: mock.Mock,
    ) -> None:
        counters = {
            "checked": 1,
            "paid": 1,
            "fulfilled": 1,
            "provider_expired": 0,
            "retryable_failed": 0,
            "notifications_enqueued": 0,
        }
        get_service.return_value.return_value = counters

        result = reconcile_crypto_payments_task.run()

        self.assertEqual(result, counters)
        logger.info.assert_called_once_with(
            "crypto_reconciliation_complete",
            extra=counters,
        )
