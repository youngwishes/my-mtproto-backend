from __future__ import annotations

import uuid
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.vpn.dtos import VPNAgentHealthDTO
from apps.vpn.enums import VPNApplyStatus, VPNDataPlaneState, VPNNodeHealthState
from apps.vpn.exceptions import VPNAgentTimeout, VPNFleetUnexpectedError
from apps.vpn.selectors import record_vpn_node_unexpected_failure
from apps.vpn.services.health_check import (
    HealthCheckVPNFleetService,
    get_health_check_vpn_node_service,
)
from apps.vpn.tests.factories import VPNNodeFactory
from apps.vpn.tests.factories import (
    VPNAccessFactory,
    VPNAccessNodeRevisionEvidenceFactory,
)


class HealthCheckVPNNodeServiceTests(TestCase):
    def test_health_exact_match_never_promotes_node_to_ready(self) -> None:
        snapshot_hash = "a" * 64
        node = VPNNodeFactory(
            health_state=VPNNodeHealthState.SYNCING,
            desired_snapshot_revision=7,
            desired_snapshot_hash=snapshot_hash,
            applied_snapshot_revision=0,
            applied_snapshot_hash="",
        )
        health = VPNAgentHealthDTO(
            contract_version="v1",
            schema_version="1.0",
            agent_sha="b" * 40,
            xray_version="1",
            xray_image_digest=f"sha256:{'c' * 64}",
            readiness="READY",
            applied_snapshot_revision=7,
            applied_snapshot_hash=snapshot_hash,
        )

        get_health_check_vpn_node_service(get_health=lambda *, node: health)(node=node)

        node.refresh_from_db()
        self.assertEqual(node.health_state, VPNNodeHealthState.SYNCING)
        self.assertEqual(node.applied_snapshot_revision, 0)

    def test_recovery_ready_marks_node_syncing_for_full_reconcile(self) -> None:
        node = VPNNodeFactory(
            health_state=VPNNodeHealthState.READY,
            desired_snapshot_revision=3,
            desired_snapshot_hash="a" * 64,
            applied_snapshot_revision=3,
            applied_snapshot_hash="a" * 64,
        )
        health = VPNAgentHealthDTO(
            contract_version="v1",
            schema_version="1.0",
            agent_sha="b" * 40,
            xray_version="1",
            xray_image_digest=f"sha256:{'c' * 64}",
            readiness="RECOVERY_READY",
            applied_snapshot_revision=None,
            applied_snapshot_hash=None,
        )

        get_health_check_vpn_node_service(get_health=lambda *, node: health)(node=node)

        node.refresh_from_db()
        self.assertEqual(node.health_state, VPNNodeHealthState.SYNCING)

    def test_recovery_ready_preserves_existing_reconcile_error(self) -> None:
        node = VPNNodeFactory(
            health_state=VPNNodeHealthState.UNHEALTHY,
            desired_snapshot_revision=3,
            desired_snapshot_hash="a" * 64,
            last_error_code="revision_conflict",
        )
        health = VPNAgentHealthDTO(
            contract_version="v1",
            schema_version="1.0",
            agent_sha="b" * 40,
            xray_version="1",
            xray_image_digest=f"sha256:{'c' * 64}",
            readiness="RECOVERY_READY",
            applied_snapshot_revision=3,
            applied_snapshot_hash="a" * 64,
        )

        get_health_check_vpn_node_service(get_health=lambda *, node: health)(node=node)

        node.refresh_from_db()
        self.assertEqual(node.health_state, VPNNodeHealthState.SYNCING)
        self.assertEqual(node.last_error_code, "revision_conflict")

    def test_revision_drift_preserves_existing_reconcile_error(self) -> None:
        node = VPNNodeFactory(
            health_state=VPNNodeHealthState.UNHEALTHY,
            desired_snapshot_revision=3,
            desired_snapshot_hash="a" * 64,
            last_error_code="snapshot_not_exact",
        )
        health = VPNAgentHealthDTO(
            contract_version="v1",
            schema_version="1.0",
            agent_sha="b" * 40,
            xray_version="1",
            xray_image_digest=f"sha256:{'c' * 64}",
            readiness="READY",
            applied_snapshot_revision=2,
            applied_snapshot_hash="d" * 64,
        )

        get_health_check_vpn_node_service(get_health=lambda *, node: health)(node=node)

        node.refresh_from_db()
        self.assertEqual(node.last_error_code, "snapshot_not_exact")

    def test_staged_desired_snapshot_keeps_confirmed_published_snapshot_serving(
        self,
    ) -> None:
        access = VPNAccessFactory(
            state="preparing",
            desired_revision=2,
            desired_uuid=uuid.uuid4(),
            published_uuid=uuid.uuid4(),
            published_revision=1,
        )
        node = VPNNodeFactory(
            health_state=VPNNodeHealthState.SYNCING,
            data_plane_state=VPNDataPlaneState.SERVING_READY,
            desired_snapshot_revision=3,
            desired_snapshot_hash="a" * 64,
            applied_snapshot_revision=2,
            applied_snapshot_hash="d" * 64,
        )
        evidence = VPNAccessNodeRevisionEvidenceFactory(
            access=access,
            node=node,
            revision=1,
            applied_revision=1,
            status=VPNApplyStatus.APPLIED,
            is_serving=True,
        )
        health = VPNAgentHealthDTO(
            contract_version="v1",
            schema_version="1.0",
            agent_sha="b" * 40,
            xray_version="1",
            xray_image_digest=f"sha256:{'c' * 64}",
            readiness="READY",
            applied_snapshot_revision=2,
            applied_snapshot_hash="d" * 64,
        )

        get_health_check_vpn_node_service(get_health=lambda *, node: health)(node=node)

        node.refresh_from_db()
        evidence.refresh_from_db()
        self.assertEqual(node.health_state, VPNNodeHealthState.SYNCING)
        self.assertEqual(node.data_plane_state, VPNDataPlaneState.SERVING_READY)
        self.assertTrue(evidence.is_serving)
        self.assertIsNotNone(node.revision_drift_started_at)

    def test_unconfirmed_snapshot_drift_revokes_serving_eligibility(self) -> None:
        access = VPNAccessFactory()
        node = VPNNodeFactory(
            health_state=VPNNodeHealthState.READY,
            data_plane_state=VPNDataPlaneState.SERVING_READY,
            desired_snapshot_revision=3,
            desired_snapshot_hash="a" * 64,
            applied_snapshot_revision=3,
            applied_snapshot_hash="a" * 64,
        )
        evidence = VPNAccessNodeRevisionEvidenceFactory(
            access=access,
            node=node,
            revision=1,
            applied_revision=1,
            status=VPNApplyStatus.APPLIED,
            is_serving=True,
        )
        health = VPNAgentHealthDTO(
            contract_version="v1",
            schema_version="1.0",
            agent_sha="b" * 40,
            xray_version="1",
            xray_image_digest=f"sha256:{'c' * 64}",
            readiness="READY",
            applied_snapshot_revision=2,
            applied_snapshot_hash="d" * 64,
        )

        get_health_check_vpn_node_service(get_health=lambda *, node: health)(node=node)

        node.refresh_from_db()
        evidence.refresh_from_db()
        self.assertEqual(node.data_plane_state, VPNDataPlaneState.UNAVAILABLE)
        self.assertFalse(evidence.is_serving)

    def test_authenticated_drift_clears_transport_failure_onset(self) -> None:
        node = VPNNodeFactory(
            health_state=VPNNodeHealthState.UNHEALTHY,
            data_plane_state=VPNDataPlaneState.UNAVAILABLE,
            desired_snapshot_revision=3,
            desired_snapshot_hash="a" * 64,
            applied_snapshot_revision=2,
            applied_snapshot_hash="d" * 64,
            last_error_code="agent_unauthorized",
            last_error_started_at=timezone.now(),
        )
        health = VPNAgentHealthDTO(
            contract_version="v1",
            schema_version="1.0",
            agent_sha="b" * 40,
            xray_version="1",
            xray_image_digest=f"sha256:{'c' * 64}",
            readiness="READY",
            applied_snapshot_revision=2,
            applied_snapshot_hash="d" * 64,
        )

        get_health_check_vpn_node_service(get_health=lambda *, node: health)(node=node)

        node.refresh_from_db()
        self.assertEqual(node.last_error_code, "")
        self.assertIsNone(node.last_error_started_at)
        self.assertIsNotNone(node.revision_drift_started_at)

    def test_transport_failure_revokes_serving_eligibility(self) -> None:
        access = VPNAccessFactory()
        node = VPNNodeFactory(
            health_state=VPNNodeHealthState.READY,
            data_plane_state=VPNDataPlaneState.SERVING_READY,
            desired_snapshot_revision=3,
            desired_snapshot_hash="a" * 64,
            applied_snapshot_revision=3,
            applied_snapshot_hash="a" * 64,
        )
        evidence = VPNAccessNodeRevisionEvidenceFactory(
            access=access,
            node=node,
            revision=1,
            applied_revision=1,
            status=VPNApplyStatus.APPLIED,
            is_serving=True,
        )

        get_health_check_vpn_node_service(
            get_health=mock.Mock(side_effect=VPNAgentTimeout(node.pk))
        )(node=node)

        node.refresh_from_db()
        evidence.refresh_from_db()
        self.assertEqual(node.data_plane_state, VPNDataPlaneState.UNAVAILABLE)
        self.assertFalse(evidence.is_serving)

    def test_fleet_reports_unexpected_failure_continues_and_raises_safe_error(
        self,
    ) -> None:
        first = VPNNodeFactory()
        second = VPNNodeFactory()
        check_node = mock.Mock(
            side_effect=[ValueError("raw-health-secret-must-not-escape"), True]
        )
        report_failure = mock.Mock()
        service = HealthCheckVPNFleetService(
            get_nodes=lambda: (first, second),
            check_node=check_node,
            record_unexpected_failure=record_vpn_node_unexpected_failure,
            report_failure=report_failure,
        )

        with self.assertRaisesRegex(
            VPNFleetUnexpectedError, "unexpected VPN fleet failure"
        ) as raised:
            service()

        self.assertNotIn("raw-health-secret", str(raised.exception))
        self.assertEqual(check_node.call_count, 2)
        first.refresh_from_db()
        self.assertEqual(first.health_state, VPNNodeHealthState.UNHEALTHY)
        self.assertEqual(first.last_error_code, "unexpected_health_error")
        report_failure.assert_called_once_with(
            node_id=first.pk,
            error_code="unexpected_health_error",
        )

    def test_fleet_isolates_expected_transport_failure(self) -> None:
        first = VPNNodeFactory()
        second = VPNNodeFactory()
        check_node = mock.Mock(side_effect=[VPNAgentTimeout(first.pk), True])

        result = HealthCheckVPNFleetService(
            get_nodes=lambda: (first, second),
            check_node=check_node,
        )()

        self.assertEqual(result.succeeded, 1)
        self.assertEqual(result.failed, 1)
        self.assertEqual(check_node.call_count, 2)
