from __future__ import annotations

from datetime import datetime

from django.db.models import F, QuerySet
from django.utils import timezone

from apps.vpn.dtos import VPNDesiredAccessDTO
from apps.vpn.enums import VPNAccessState, VPNNodeHealthState
from apps.vpn.models import VPNAccess, VPNAccessNodeApply, VPNNode, VPNPurchase


def get_vpn_access_by_user_id(*, user_id: int) -> VPNAccess | None:
    return VPNAccess.objects.active().filter(user_id=user_id).first()


def get_any_vpn_access_by_user_id(*, user_id: int) -> VPNAccess | None:
    """Return the unique access regardless of lifecycle state."""
    return VPNAccess.objects.filter(user_id=user_id).first()


def get_vpn_purchase_by_payment_id(*, payment_id: int) -> VPNPurchase | None:
    """Return the immutable fulfillment audit for exact payment replay."""
    return VPNPurchase.objects.filter(payment_id=payment_id).select_related("access").first()


def get_vpn_access_by_subscription_token(*, token: str) -> VPNAccess | None:
    return VPNAccess.objects.active().filter(subscription_token=token).first()


def get_active_unexpired_vpn_access_by_user_id(*, user_id: int) -> VPNAccess | None:
    """Return an access whose credential already occupies snapshot capacity."""
    return (
        VPNAccess.objects.active()
        .filter(
            user_id=user_id,
            expired_at__gt=timezone.now(),
            state__in=(VPNAccessState.PREPARING, VPNAccessState.READY),
        )
        .first()
    )


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


def get_desired_vpn_snapshot_accesses(
    *, at: datetime | None = None
) -> tuple[VPNDesiredAccessDTO, ...]:
    """Return desired credentials; expiry and deactivation are represented by absence."""
    effective_at = at or timezone.now()
    rows = (
        VPNAccess.objects.active()
        .filter(
            expired_at__gt=effective_at,
            disabled_at__isnull=True,
            state__in=(VPNAccessState.PREPARING, VPNAccessState.READY),
        )
        .order_by("pk")
        .values_list("pk", "desired_uuid", "desired_revision", "user_id")
    )
    return tuple(
        VPNDesiredAccessDTO(
            access_id=access_id,
            uuid=desired_uuid,
            access_revision=desired_revision,
            customer_id=customer_id,
        )
        for access_id, desired_uuid, desired_revision, customer_id in rows
    )


def has_compatible_ready_vpn_node_with_capacity(
    *,
    contract_version: str,
    max_snapshot_entries: int,
    prospective_increment: int,
) -> bool:
    """Return whether a first purchase or renewal fits a compatible node."""
    current_access_count = (
        VPNAccess.objects.active()
        .filter(
            expired_at__gt=timezone.now(),
            state__in=(VPNAccessState.PREPARING, VPNAccessState.READY),
        )
        .count()
    )
    if current_access_count + prospective_increment > max_snapshot_entries:
        return False
    return (
        get_ready_available_vpn_nodes()
        .filter(
            agent_contract_version=contract_version,
        )
        .exists()
    )
