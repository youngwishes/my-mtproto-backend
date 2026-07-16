from __future__ import annotations

from celery import shared_task

from apps.vpn.observability import get_collect_vpn_observability_service


@shared_task(name="apps.vpn.collect_observability")
def collect_vpn_observability_task() -> dict[str, int]:
    observation = get_collect_vpn_observability_service()()
    return {
        "metrics": len(observation.metrics),
        "alerts": len(observation.alerts),
    }


__all__ = ["collect_vpn_observability_task"]
