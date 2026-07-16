from __future__ import annotations

from celery import shared_task

from apps.vpn.services.health_check import get_health_check_vpn_fleet_service
from apps.vpn.services.reconcile import get_reconcile_vpn_fleet_service
from apps.vpn.services.expire_accesses import get_expire_vpn_accesses_service
from apps.vpn.observability import VPNMetric, emit_vpn_metric
from apps.vpn.exceptions import VPNFleetUnexpectedError


@shared_task(name="apps.vpn.health_check_nodes")
def health_check_vpn_nodes_task() -> dict[str, int]:
    result = get_health_check_vpn_fleet_service()()
    return {"succeeded": result.succeeded, "failed": result.failed}


@shared_task(name="apps.vpn.reconcile_nodes")
def reconcile_vpn_nodes_task() -> dict[str, int]:
    try:
        result = get_reconcile_vpn_fleet_service()()
    except VPNFleetUnexpectedError:
        try:
            emit_vpn_metric(
                VPNMetric(name="vpn_reconcile_delivery_failure_total", value=1)
            )
        except Exception:
            pass
        raise
    for metric in (
        VPNMetric(name="vpn_reconcile_delivery_success_total", value=result.succeeded),
        VPNMetric(name="vpn_reconcile_delivery_failure_total", value=result.failed),
    ):
        try:
            emit_vpn_metric(metric)
        except Exception:
            pass
    return {"succeeded": result.succeeded, "failed": result.failed}


@shared_task(name="apps.vpn.expire_accesses")
def expire_vpn_accesses_task() -> int:
    return get_expire_vpn_accesses_service()()
