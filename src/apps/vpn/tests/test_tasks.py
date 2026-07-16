from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase

from apps.vpn.tasks.reconcile import (
    health_check_vpn_nodes_task,
    reconcile_vpn_nodes_task,
)


class VPNTaskTests(SimpleTestCase):
    @mock.patch("apps.vpn.tasks.reconcile.get_reconcile_vpn_fleet_service")
    def test_reconcile_task_is_thin(self, factory: mock.Mock) -> None:
        factory.return_value.return_value.succeeded = 2
        factory.return_value.return_value.failed = 1

        result = reconcile_vpn_nodes_task.run()

        self.assertEqual(result, {"succeeded": 2, "failed": 1})

    def test_beat_has_health_reconcile_and_notification_recovery(self) -> None:
        schedule = settings.CELERY_BEAT_SCHEDULE
        self.assertEqual(
            schedule["health-check-vpn-nodes"]["schedule"], timedelta(minutes=5)
        )
        self.assertEqual(
            schedule["reconcile-vpn-nodes"]["schedule"], timedelta(hours=1)
        )
        self.assertEqual(
            schedule["recover-vpn-ready-notifications"]["schedule"],
            timedelta(minutes=1),
        )
        self.assertEqual(
            schedule["health-check-vpn-nodes"]["task"],
            health_check_vpn_nodes_task.name,
        )
