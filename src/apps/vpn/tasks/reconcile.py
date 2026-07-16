from __future__ import annotations

from celery import shared_task

from apps.vpn.services.health_check import get_health_check_vpn_fleet_service
from apps.vpn.services.reconcile import get_reconcile_vpn_fleet_service
from apps.vpn.services.expire_accesses import get_expire_vpn_accesses_service


@shared_task(name="apps.vpn.health_check_nodes")
def health_check_vpn_nodes_task() -> dict[str, int]:
    result = get_health_check_vpn_fleet_service()()
    return {"succeeded": result.succeeded, "failed": result.failed}


@shared_task(name="apps.vpn.reconcile_nodes")
def reconcile_vpn_nodes_task() -> dict[str, int]:
    result = get_reconcile_vpn_fleet_service()()
    return {"succeeded": result.succeeded, "failed": result.failed}


@shared_task(name="apps.vpn.expire_accesses")
def expire_vpn_accesses_task() -> int:
    return get_expire_vpn_accesses_service()()
