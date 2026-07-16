from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.vpn.dtos import VPNAgentApplyResultDTO, VPNAgentHealthDTO
from apps.vpn.enums import VPNApplyStatus, VPNNodeHealthState
from apps.vpn.exceptions import (
    VPNAgentContractError,
    VPNAgentRevisionConflict,
    VPNAgentSnapshotOverflow,
    VPNAgentStaleRevision,
    VPNAgentTimeout,
    VPNFleetUnexpectedError,
)
from apps.vpn.services.reconcile import (
    ReconcileVPNNodeService,
    ReconcileVPNFleetService,
    get_reconcile_vpn_node_service,
)
from apps.vpn.services.publish_readiness import get_publish_vpn_readiness_service
from apps.vpn.selectors import record_vpn_node_unexpected_failure
from apps.vpn.services.health_check import get_health_check_vpn_node_service
from apps.vpn.services.build_snapshot import get_build_vpn_snapshot_service
from apps.vpn.tests.factories import VPNAccessFactory, VPNNodeFactory


class FakeAgentClient:
    def __init__(
        self, *, error: Exception | None = None, readiness: str = "READY"
    ) -> None:
        self.error = error
        self.readiness = readiness
        self.snapshots = []

    def put_snapshot(self, *, node, snapshot):
        if self.error is not None:
            raise self.error
        self.snapshots.append(snapshot)
        return VPNAgentApplyResultDTO(
            schema_version=snapshot.schema_version,
            snapshot_revision=snapshot.snapshot_revision,
            snapshot_hash=snapshot.snapshot_hash,
            result="applied",
        )

    def get_health(self, *, node):
        snapshot = self.snapshots[-1]
        return VPNAgentHealthDTO(
            contract_version=node.contract_version,
            schema_version=snapshot.schema_version,
            agent_sha="a" * 40,
            xray_version="1",
            xray_image_digest=f"sha256:{'b' * 64}",
            readiness=self.readiness,
            applied_snapshot_revision=snapshot.snapshot_revision,
            applied_snapshot_hash=snapshot.snapshot_hash,
        )


class FlakyAgentClient(FakeAgentClient):
    def __init__(self, *, failures: int) -> None:
        super().__init__()
        self.failures = failures
        self.put_attempts = 0

    def put_snapshot(self, *, node, snapshot):
        self.put_attempts += 1
        if self.put_attempts <= self.failures:
            raise VPNAgentTimeout(node.node_id)
        return super().put_snapshot(node=node, snapshot=snapshot)


class ReconcileVPNNodeServiceTests(TestCase):
    def setUp(self) -> None:
        self.access = VPNAccessFactory()
        self.node = VPNNodeFactory()

    def test_full_snapshot_advances_revision_and_marks_exact_apply_ready(self) -> None:
        client = FakeAgentClient()

        get_reconcile_vpn_node_service(client=client)(node=self.node)

        self.node.refresh_from_db()
        evidence = self.node.access_applies.get(access=self.access)
        self.assertEqual(self.node.desired_snapshot_revision, 1)
        self.assertEqual(self.node.applied_snapshot_revision, 1)
        self.assertEqual(
            self.node.applied_snapshot_hash, self.node.desired_snapshot_hash
        )
        self.assertEqual(self.node.health_state, VPNNodeHealthState.READY)
        self.assertEqual(evidence.status, VPNApplyStatus.APPLIED)
        self.assertEqual(evidence.applied_revision, self.access.desired_revision)

    def test_lost_task_reuses_staged_revision_instead_of_advancing_it(self) -> None:
        client = FakeAgentClient()
        service = get_reconcile_vpn_node_service(client=client)
        service(node=self.node)
        self.node.refresh_from_db()
        staged_revision = self.node.desired_snapshot_revision
        self.node.applied_snapshot_revision = 0
        self.node.applied_snapshot_hash = ""
        self.node.health_state = VPNNodeHealthState.SYNCING
        self.node.save(
            update_fields=(
                "applied_snapshot_revision",
                "applied_snapshot_hash",
                "health_state",
                "updated_at",
            )
        )

        service(node=self.node)

        self.node.refresh_from_db()
        self.assertEqual(self.node.desired_snapshot_revision, staged_revision)
        self.assertEqual(client.snapshots[-1].snapshot_revision, staged_revision)

    def test_changed_desired_set_advances_revision_monotonically(self) -> None:
        client = FakeAgentClient()
        service = get_reconcile_vpn_node_service(client=client)
        service(node=self.node)
        VPNAccessFactory()

        service(node=self.node)

        self.node.refresh_from_db()
        self.assertEqual(self.node.desired_snapshot_revision, 2)
        self.assertEqual(self.node.applied_snapshot_revision, 2)

    def test_successful_removal_invalidates_apply_before_same_revision_renewal(
        self,
    ) -> None:
        client = FakeAgentClient()
        publish = get_publish_vpn_readiness_service()
        service = get_reconcile_vpn_node_service(
            client=client,
            publish_access=publish,
        )
        service(node=self.node)
        self.access.refresh_from_db()
        self.assertEqual(self.access.state, "ready")

        self.access.expired_at = timezone.now()
        self.access.save(update_fields=("expired_at", "updated_at"))
        service(node=self.node)

        evidence = self.node.access_applies.get(access=self.access)
        self.assertIsNone(evidence.applied_revision)
        self.assertNotEqual(evidence.status, VPNApplyStatus.APPLIED)

        original_revision = self.access.desired_revision
        self.access.expired_at = timezone.now() + timedelta(days=30)
        self.access.state = "preparing"
        self.access.save(update_fields=("expired_at", "state", "updated_at"))

        self.assertFalse(publish(access_id=self.access.pk))
        self.access.refresh_from_db()
        self.assertEqual(self.access.desired_revision, original_revision)
        self.assertEqual(self.access.state, "preparing")

        self.assertTrue(service(node=self.node))
        self.access.refresh_from_db()
        self.assertEqual(self.access.state, "ready")

    def test_failed_removal_preserves_prior_published_pair_and_apply_evidence(
        self,
    ) -> None:
        client = FakeAgentClient()
        publish = get_publish_vpn_readiness_service()
        service = get_reconcile_vpn_node_service(
            client=client,
            publish_access=publish,
        )
        service(node=self.node)
        self.access.refresh_from_db()
        published_pair = (
            self.access.published_uuid,
            self.access.published_revision,
        )
        self.access.expired_at = timezone.now()
        self.access.save(update_fields=("expired_at", "updated_at"))
        failing_service = get_reconcile_vpn_node_service(
            client=FakeAgentClient(error=VPNAgentRevisionConflict(self.node.pk)),
            publish_access=publish,
        )

        self.assertFalse(failing_service(node=self.node))

        self.access.refresh_from_db()
        evidence = self.node.access_applies.get(access=self.access)
        self.assertEqual(
            (self.access.published_uuid, self.access.published_revision),
            published_pair,
        )
        self.assertTrue(evidence.is_active)
        self.assertEqual(evidence.status, VPNApplyStatus.APPLIED)

    def test_failure_is_mapped_to_safe_observable_state(self) -> None:
        cases = (
            (VPNAgentContractError(self.node.pk), VPNNodeHealthState.INCOMPATIBLE),
            (VPNAgentSnapshotOverflow(self.node.pk), VPNNodeHealthState.OVER_CAPACITY),
            (VPNAgentStaleRevision(self.node.pk), VPNNodeHealthState.UNHEALTHY),
            (VPNAgentRevisionConflict(self.node.pk), VPNNodeHealthState.UNHEALTHY),
        )
        for error, expected_state in cases:
            with self.subTest(error=error.error_code):
                get_reconcile_vpn_node_service(client=FakeAgentClient(error=error))(
                    node=self.node
                )
                self.node.refresh_from_db()
                self.assertEqual(self.node.health_state, expected_state)
                self.assertEqual(self.node.last_error_code, error.error_code)

    def test_repeated_same_failure_emits_one_deduplicated_safe_alert(self) -> None:
        report_failure = mock.Mock()
        service = get_reconcile_vpn_node_service(
            client=FakeAgentClient(error=VPNAgentRevisionConflict(self.node.pk)),
            report_failure=report_failure,
        )

        service(node=self.node)
        service(node=self.node)

        report_failure.assert_called_once_with(
            node_id=self.node.pk,
            error_code="revision_conflict",
        )

    def test_health_tick_does_not_break_reconcile_alert_deduplication(self) -> None:
        report_failure = mock.Mock()
        service = get_reconcile_vpn_node_service(
            client=FakeAgentClient(error=VPNAgentRevisionConflict(self.node.pk)),
            report_failure=report_failure,
        )
        service(node=self.node)
        self.node.refresh_from_db()
        health = VPNAgentHealthDTO(
            contract_version="v1",
            schema_version="1.0",
            agent_sha="a" * 40,
            xray_version="1",
            xray_image_digest=f"sha256:{'b' * 64}",
            readiness="READY",
            applied_snapshot_revision=self.node.desired_snapshot_revision,
            applied_snapshot_hash=self.node.desired_snapshot_hash,
        )
        get_health_check_vpn_node_service(get_health=lambda *, node: health)(
            node=self.node
        )

        service(node=self.node)

        report_failure.assert_called_once()

    def test_recovery_ready_after_put_remains_syncing(self) -> None:
        result = get_reconcile_vpn_node_service(
            client=FakeAgentClient(readiness="RECOVERY_READY")
        )(node=self.node)

        self.assertFalse(result)
        self.node.refresh_from_db()
        self.assertEqual(self.node.health_state, VPNNodeHealthState.SYNCING)
        self.assertEqual(self.node.last_error_code, "recovery_ready")
        self.assertEqual(self.node.applied_snapshot_revision, 0)

    def test_transient_delivery_retry_is_bounded_and_recovers(self) -> None:
        client = FlakyAgentClient(failures=2)
        service = get_reconcile_vpn_node_service(client=client)
        sleep = mock.Mock()
        object.__setattr__(service, "sleep", sleep)
        object.__setattr__(service, "jitter", lambda start, end: start)

        result = service(node=self.node)

        self.assertTrue(result)
        self.assertEqual(client.put_attempts, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_conditional_prepare_retry_is_bounded_and_jittered(self) -> None:
        stage_snapshot = mock.Mock(return_value=False)
        sleep = mock.Mock()
        service = ReconcileVPNNodeService(
            build_snapshot=get_build_vpn_snapshot_service(),
            client=mock.Mock(),
            refresh_node=lambda **kwargs: self.node,
            stage_snapshot=stage_snapshot,
            mark_pending_applies=mock.Mock(),
            mark_applied=mock.Mock(),
            mark_failed=mock.Mock(),
            publish_access=mock.Mock(),
            report_failure=mock.Mock(),
            now=mock.Mock(),
            sleep=sleep,
            jitter=lambda start, end: 0.025,
            max_prepare_attempts=3,
        )

        result = service(node=self.node)

        self.assertFalse(result)
        self.assertEqual(stage_snapshot.call_count, 3)
        self.assertEqual(sleep.call_args_list, [mock.call(0.025), mock.call(0.025)])
        service.client.put_snapshot.assert_not_called()

    def test_fleet_isolates_one_node_failure(self) -> None:
        other = VPNNodeFactory()
        reconcile_node = mock.Mock(side_effect=[VPNAgentTimeout(self.node.pk), True])
        service = ReconcileVPNFleetService(
            get_nodes=lambda: (self.node, other), reconcile_node=reconcile_node
        )

        result = service()

        self.assertEqual(result.succeeded, 1)
        self.assertEqual(result.failed, 1)
        self.assertEqual(reconcile_node.call_count, 2)

    def test_fleet_reports_unexpected_failure_continues_and_raises_safe_error(
        self,
    ) -> None:
        other = VPNNodeFactory()
        reconcile_node = mock.Mock(
            side_effect=[ValueError("raw-secret-must-not-escape"), True]
        )
        report_failure = mock.Mock()
        service = ReconcileVPNFleetService(
            get_nodes=lambda: (self.node, other),
            reconcile_node=reconcile_node,
            record_unexpected_failure=record_vpn_node_unexpected_failure,
            report_failure=report_failure,
        )

        with self.assertRaisesRegex(
            VPNFleetUnexpectedError, "unexpected VPN fleet failure"
        ) as raised:
            service()

        self.assertNotIn("raw-secret", str(raised.exception))
        self.assertEqual(reconcile_node.call_count, 2)
        self.node.refresh_from_db()
        self.assertEqual(self.node.health_state, VPNNodeHealthState.UNHEALTHY)
        self.assertEqual(self.node.last_error_code, "unexpected_reconcile_error")
        report_failure.assert_called_once_with(
            node_id=self.node.pk,
            error_code="unexpected_reconcile_error",
        )

    def test_fleet_reports_all_node_failure_without_aborting_iteration(self) -> None:
        other = VPNNodeFactory()
        reconcile_node = mock.Mock(return_value=False)

        result = ReconcileVPNFleetService(
            get_nodes=lambda: (self.node, other),
            reconcile_node=reconcile_node,
            record_unexpected_failure=mock.Mock(),
            report_failure=mock.Mock(),
        )()

        self.assertEqual(result.succeeded, 0)
        self.assertEqual(result.failed, 2)
        self.assertEqual(reconcile_node.call_count, 2)
