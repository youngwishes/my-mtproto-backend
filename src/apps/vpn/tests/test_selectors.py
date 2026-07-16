from __future__ import annotations

from django.db import connection
from django.test import TestCase

from apps.vpn.selectors import get_ready_available_vpn_nodes
from apps.vpn.tests.factories import VPNNodeFactory


class ReadyAvailableVPNNodesSelectorTests(TestCase):
    def test_returns_only_exact_nonzero_synchronized_ready_nodes(self) -> None:
        synchronized = VPNNodeFactory(
            health_state="ready",
            desired_snapshot_revision=1,
            desired_snapshot_hash="a" * 64,
            applied_snapshot_revision=1,
            applied_snapshot_hash="a" * 64,
        )
        VPNNodeFactory(
            health_state="syncing",
            desired_snapshot_revision=2,
            desired_snapshot_hash="b" * 64,
            applied_snapshot_revision=1,
            applied_snapshot_hash="a" * 64,
        )
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA ignore_check_constraints = ON")
        try:
            VPNNodeFactory(health_state="ready")
            VPNNodeFactory(
                health_state="ready",
                desired_snapshot_revision=2,
                desired_snapshot_hash="b" * 64,
                applied_snapshot_revision=1,
                applied_snapshot_hash="a" * 64,
            )
            VPNNodeFactory(
                health_state="ready",
                desired_snapshot_revision=1,
                desired_snapshot_hash="a" * 64,
                applied_snapshot_revision=1,
                applied_snapshot_hash="b" * 64,
            )
        finally:
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA ignore_check_constraints = OFF")

        self.assertEqual(list(get_ready_available_vpn_nodes()), [synchronized])
