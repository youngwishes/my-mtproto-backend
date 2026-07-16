from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import logging
from typing import final

from apps.vpn.dtos import VPNAgentHealthDTO
from apps.vpn.exceptions import VPNAgentTransportError, VPNFleetUnexpectedError
from apps.vpn.models import VPNNode
from apps.vpn.selectors import (
    get_active_vpn_nodes,
    record_vpn_node_health,
    record_vpn_node_health_failure,
    record_vpn_node_unexpected_failure,
)
from apps.vpn.services.reconcile import VPNFleetRunResult, _node_dto

logger = logging.getLogger(__name__)


def _noop_record_unexpected_failure(*, node: VPNNode, error_code: str) -> None:
    return None


def _noop_report_failure(*, node_id: int, error_code: str) -> None:
    return None


def _report_failure(*, node_id: int, error_code: str) -> None:
    logger.warning(
        "vpn_node_health_failed",
        extra={"node_id": node_id, "error_code": error_code},
    )


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class HealthCheckVPNNodeService:
    get_health: Callable[..., VPNAgentHealthDTO]
    record_health: Callable[..., None]
    record_failure: Callable[..., None]

    def __call__(self, *, node: VPNNode) -> bool:
        try:
            health = self.get_health(node=_node_dto(node=node))
        except VPNAgentTransportError as exc:
            self.record_failure(node=node, error=exc)
            return False
        self.record_health(node=node, health=health)
        return health.readiness == "READY"


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class HealthCheckVPNFleetService:
    get_nodes: Callable[[], Iterable[VPNNode]]
    check_node: Callable[..., bool]
    record_unexpected_failure: Callable[..., None] = _noop_record_unexpected_failure
    report_failure: Callable[..., None] = _noop_report_failure

    def __call__(self) -> VPNFleetRunResult:
        succeeded = 0
        failed = 0
        unexpected_failure = False
        for node in self.get_nodes():
            try:
                result = self.check_node(node=node)
            except VPNAgentTransportError:
                result = False
            except Exception:
                unexpected_failure = True
                result = False
                try:
                    self.record_unexpected_failure(
                        node=node,
                        error_code="unexpected_health_error",
                    )
                except Exception:
                    pass
                try:
                    self.report_failure(
                        node_id=node.pk,
                        error_code="unexpected_health_error",
                    )
                except Exception:
                    pass
            succeeded += int(result)
            failed += int(not result)
        if unexpected_failure:
            raise VPNFleetUnexpectedError() from None
        return VPNFleetRunResult(succeeded=succeeded, failed=failed)


def get_health_check_vpn_node_service(
    *, get_health: Callable[..., VPNAgentHealthDTO] | None = None
) -> HealthCheckVPNNodeService:
    if get_health is None:
        from apps.vpn.infra import get_vpn_agent_transport

        get_health = get_vpn_agent_transport().get_health
    return HealthCheckVPNNodeService(
        get_health=get_health,
        record_health=record_vpn_node_health,
        record_failure=record_vpn_node_health_failure,
    )


def get_health_check_vpn_fleet_service() -> HealthCheckVPNFleetService:
    return HealthCheckVPNFleetService(
        get_nodes=get_active_vpn_nodes,
        check_node=get_health_check_vpn_node_service(),
        record_unexpected_failure=record_vpn_node_unexpected_failure,
        report_failure=_report_failure,
    )
