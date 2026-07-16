from __future__ import annotations

from django.db.models import F, QuerySet

from apps.vpn.enums import VPNNodeHealthState
from apps.vpn.models import VPNAccess, VPNAccessNodeApply, VPNNode


def get_vpn_access_by_user_id(*, user_id: int) -> VPNAccess | None:
    return VPNAccess.objects.active().filter(user_id=user_id).first()


def get_vpn_access_by_subscription_token(*, token: str) -> VPNAccess | None:
    return VPNAccess.objects.active().filter(subscription_token=token).first()


def get_ready_available_vpn_nodes() -> QuerySet[VPNNode]:
    return VPNNode.objects.active().filter(
        health_state=VPNNodeHealthState.READY,
        is_access_available=True,
        desired_snapshot_revision__gt=0,
        applied_snapshot_revision=F("desired_snapshot_revision"),
        applied_snapshot_hash=F("desired_snapshot_hash"),
    ).exclude(desired_snapshot_hash="")


def get_access_node_applies(*, access: VPNAccess) -> QuerySet[VPNAccessNodeApply]:
    return VPNAccessNodeApply.objects.active().filter(access=access).select_related("node")
