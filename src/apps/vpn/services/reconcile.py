from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import logging
import random
import time
from typing import TYPE_CHECKING, final

from django.utils import timezone
from django.db import transaction

from apps.vpn.dtos import VPNAgentNodeDTO, VPNExactSnapshotDTO
from apps.vpn.enums import VPNNodeHealthState
from apps.vpn.exceptions import (
    VPNAgentContractError,
    VPNAgentSnapshotOverflow,
    VPNAgentTimeout,
    VPNAgentTransportError,
    VPNAgentUnavailable,
    VPNFleetUnexpectedError,
)
from apps.vpn.models import VPNNode
from apps.vpn.protocols import VPNAgentClient
from apps.vpn.selectors import (
    get_active_vpn_nodes,
    get_vpn_node_by_id,
    mark_vpn_node_snapshot_applied,
    mark_vpn_node_snapshot_failed,
    mark_vpn_snapshot_applies_pending,
    record_vpn_node_unexpected_failure,
    stage_vpn_node_snapshot,
)
from apps.vpn.services.build_snapshot import get_build_vpn_snapshot_service

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(kw_only=True, slots=True, frozen=True)
class VPNFleetRunResult:
    succeeded: int
    failed: int


def _node_dto(*, node: VPNNode) -> VPNAgentNodeDTO:
    return VPNAgentNodeDTO(
        node_id=node.pk,
        base_url=node.agent_base_url,
        secret_key=node.agent_secret_key,
        contract_version=node.agent_contract_version,
    )


def _noop_publish_access(*, access_id: int) -> bool:
    return False


def _report_failure(*, node_id: int, error_code: str) -> None:
    logger.warning(
        "vpn_node_reconcile_failed",
        extra={"error_code": error_code},
    )


def _noop_record_unexpected_failure(*, node: VPNNode, error_code: str) -> None:
    return None


def _noop_report_failure(*, node_id: int, error_code: str) -> None:
    return None


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReconcileVPNNodeService:
    build_snapshot: Callable[..., VPNExactSnapshotDTO]
    client: VPNAgentClient
    refresh_node: Callable[..., VPNNode | None]
    stage_snapshot: Callable[..., bool]
    mark_pending_applies: Callable[..., None]
    mark_applied: Callable[..., bool]
    mark_failed: Callable[..., None]
    publish_access: Callable[..., bool]
    report_failure: Callable[..., None]
    now: Callable[[], datetime]
    sleep: Callable[[float], None]
    jitter: Callable[[float, float], float]
    max_prepare_attempts: int = 3
    max_delivery_attempts: int = 3

    def __call__(self, *, node: VPNNode) -> bool:
        prepared = self._prepare_snapshot(node=node)
        if prepared is None:
            return False
        current_node, snapshot = prepared
        self.mark_pending_applies(node=current_node, snapshot=snapshot)
        health = None
        delivery_error = None
        for attempt in range(self.max_delivery_attempts):
            try:
                self.client.put_snapshot(
                    node=_node_dto(node=current_node), snapshot=snapshot
                )
                health = self.client.get_health(node=_node_dto(node=current_node))
                break
            except VPNAgentTransportError as exc:
                delivery_error = exc
                if (
                    not isinstance(exc, (VPNAgentTimeout, VPNAgentUnavailable))
                    or attempt + 1 >= self.max_delivery_attempts
                ):
                    break
                self.sleep(self.jitter(0.25, 0.75) * (2**attempt))
        if delivery_error is not None and health is None:
            self._record_failure(
                node=current_node,
                snapshot=snapshot,
                code=delivery_error.error_code,
                state=self._failure_state(error=delivery_error),
            )
            return False
        assert health is not None
        if (
            health.readiness != "READY"
            or health.applied_snapshot_revision != snapshot.snapshot_revision
            or health.applied_snapshot_hash != snapshot.snapshot_hash
        ):
            code = (
                "recovery_ready"
                if health.readiness == "RECOVERY_READY"
                else "snapshot_not_exact"
            )
            self._record_failure(
                node=current_node,
                snapshot=snapshot,
                code=code,
                state=VPNNodeHealthState.SYNCING,
            )
            return False
        with transaction.atomic():
            if not self.mark_applied(node=current_node, snapshot=snapshot, now=self.now()):
                return False
            for access in snapshot.accesses:
                self.publish_access(access_id=access.access_id)
        return True

    def _prepare_snapshot(
        self, *, node: VPNNode
    ) -> tuple[VPNNode, VPNExactSnapshotDTO] | None:
        current = node
        for attempt in range(self.max_prepare_attempts):
            refreshed = self.refresh_node(node_id=current.pk)
            if refreshed is None:
                return None
            current = refreshed
            if current.desired_snapshot_revision > 0:
                staged = self.build_snapshot(
                    snapshot_revision=current.desired_snapshot_revision
                )
                if staged.snapshot_hash == current.desired_snapshot_hash:
                    return current, staged
            candidate = self.build_snapshot(
                snapshot_revision=current.desired_snapshot_revision + 1
            )
            if self.stage_snapshot(node=current, snapshot=candidate, now=self.now()):
                current.desired_snapshot_revision = candidate.snapshot_revision
                current.desired_snapshot_hash = candidate.snapshot_hash
                current.health_state = VPNNodeHealthState.SYNCING
                return current, candidate
            if attempt + 1 < self.max_prepare_attempts:
                self.sleep(self.jitter(0.01, 0.05))
        return None

    def _record_failure(
        self,
        *,
        node: VPNNode,
        snapshot: VPNExactSnapshotDTO,
        code: str,
        state: str,
    ) -> None:
        changed = self.mark_failed(
            node=node,
            snapshot=snapshot,
            state=state,
            code=code,
            now=self.now(),
        )
        if changed:
            self.report_failure(node_id=node.pk, error_code=code)

    @staticmethod
    def _failure_state(*, error: VPNAgentTransportError) -> str:
        if isinstance(error, VPNAgentContractError):
            return VPNNodeHealthState.INCOMPATIBLE
        if isinstance(error, VPNAgentSnapshotOverflow):
            return VPNNodeHealthState.OVER_CAPACITY
        return VPNNodeHealthState.UNHEALTHY


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReconcileVPNFleetService:
    get_nodes: Callable[[], Iterable[VPNNode]]
    reconcile_node: Callable[..., bool | None]
    record_unexpected_failure: Callable[..., None] = _noop_record_unexpected_failure
    report_failure: Callable[..., None] = _noop_report_failure

    def __call__(self) -> VPNFleetRunResult:
        succeeded = 0
        failed = 0
        unexpected_failure = False
        for node in self.get_nodes():
            try:
                result = self.reconcile_node(node=node)
            except VPNAgentTransportError:
                result = False
            except Exception:
                unexpected_failure = True
                result = False
                try:
                    self.record_unexpected_failure(
                        node=node,
                        error_code="unexpected_reconcile_error",
                    )
                except Exception:
                    pass
                try:
                    self.report_failure(
                        node_id=node.pk,
                        error_code="unexpected_reconcile_error",
                    )
                except Exception:
                    pass
            if result is True:
                succeeded += 1
            else:
                failed += 1
        if unexpected_failure:
            raise VPNFleetUnexpectedError() from None
        return VPNFleetRunResult(succeeded=succeeded, failed=failed)


def get_reconcile_vpn_node_service(
    *,
    client: VPNAgentClient | None = None,
    publish_access: Callable[..., bool] = _noop_publish_access,
    report_failure: Callable[..., None] = _report_failure,
) -> ReconcileVPNNodeService:
    if client is None:
        from apps.vpn.infra import get_vpn_agent_transport

        client = get_vpn_agent_transport()
    return ReconcileVPNNodeService(
        build_snapshot=get_build_vpn_snapshot_service(),
        client=client,
        refresh_node=get_vpn_node_by_id,
        stage_snapshot=stage_vpn_node_snapshot,
        mark_pending_applies=mark_vpn_snapshot_applies_pending,
        mark_applied=mark_vpn_node_snapshot_applied,
        mark_failed=mark_vpn_node_snapshot_failed,
        publish_access=publish_access,
        report_failure=report_failure,
        now=timezone.now,
        sleep=time.sleep,
        jitter=random.uniform,
    )


def get_reconcile_vpn_fleet_service() -> ReconcileVPNFleetService:
    from apps.vpn.services.publish_readiness import (
        get_publish_vpn_readiness_service,
    )
    from apps.vpn.tasks.notifications import _enqueue_notification

    reconcile_node = get_reconcile_vpn_node_service(
        publish_access=get_publish_vpn_readiness_service(
            schedule_notification=_enqueue_notification
        )
    )
    return ReconcileVPNFleetService(
        get_nodes=get_active_vpn_nodes,
        reconcile_node=reconcile_node,
        record_unexpected_failure=record_vpn_node_unexpected_failure,
        report_failure=_report_failure,
    )
