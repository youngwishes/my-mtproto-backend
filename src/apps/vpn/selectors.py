from __future__ import annotations

from datetime import datetime

from django.db import transaction
from django.db.models import Exists, F, OuterRef, Q, QuerySet
from django.utils import timezone

from apps.vpn.dtos import (
    VPNAgentHealthDTO,
    VPNDesiredAccessDTO,
    VPNExactSnapshotDTO,
)
from apps.vpn.enums import VPNAccessState, VPNApplyStatus, VPNNodeHealthState
from apps.vpn.exceptions import VPNAgentContractError, VPNAgentTransportError
from apps.vpn.models import VPNAccess, VPNAccessNodeApply, VPNNode, VPNPurchase


def get_vpn_access_by_user_id(*, user_id: int) -> VPNAccess | None:
    return VPNAccess.objects.active().filter(user_id=user_id).first()


def get_any_vpn_access_by_user_id(*, user_id: int) -> VPNAccess | None:
    """Return the unique access regardless of lifecycle state."""
    return VPNAccess.objects.filter(user_id=user_id).first()


def get_vpn_purchase_by_payment_id(*, payment_id: int) -> VPNPurchase | None:
    """Return the immutable fulfillment audit for exact payment replay."""
    return (
        VPNPurchase.objects.filter(payment_id=payment_id)
        .select_related("access")
        .first()
    )


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
    return (
        VPNNode.objects.active()
        .filter(
            health_state=VPNNodeHealthState.READY,
            is_access_available=True,
            desired_snapshot_revision__gt=0,
            applied_snapshot_revision=F("desired_snapshot_revision"),
            applied_snapshot_hash=F("desired_snapshot_hash"),
        )
        .exclude(desired_snapshot_hash="")
    )


def get_active_vpn_nodes() -> QuerySet[VPNNode]:
    """Return all managed nodes in stable fleet order."""
    return VPNNode.objects.active().order_by("number")


def get_vpn_node_by_id(*, node_id: int) -> VPNNode | None:
    return VPNNode.objects.active().filter(pk=node_id).first()


def stage_vpn_node_snapshot(
    *, node: VPNNode, snapshot: VPNExactSnapshotDTO, now: datetime
) -> bool:
    return (
        VPNNode.objects.active()
        .filter(
            pk=node.pk,
            desired_snapshot_revision=node.desired_snapshot_revision,
            desired_snapshot_hash=node.desired_snapshot_hash,
        )
        .update(
            desired_snapshot_revision=snapshot.snapshot_revision,
            desired_snapshot_hash=snapshot.snapshot_hash,
            health_state=VPNNodeHealthState.SYNCING,
            last_error_code="",
            updated_at=now,
        )
        == 1
    )


def mark_vpn_snapshot_applies_pending(
    *, node: VPNNode, snapshot: VPNExactSnapshotDTO
) -> None:
    now = timezone.now()
    for access in snapshot.accesses:
        VPNAccessNodeApply.objects.update_or_create(
            access_id=access.access_id,
            node_id=node.pk,
            defaults={
                "desired_revision": access.access_revision,
                "applied_revision": None,
                "status": VPNApplyStatus.PENDING,
                "last_attempt_at": now,
                "last_error_code": "",
                "is_active": True,
            },
        )


def mark_vpn_node_snapshot_applied(
    *, node: VPNNode, snapshot: VPNExactSnapshotDTO, now: datetime
) -> bool:
    with transaction.atomic():
        updated = (
            VPNNode.objects.active()
            .filter(
                pk=node.pk,
                desired_snapshot_revision=snapshot.snapshot_revision,
                desired_snapshot_hash=snapshot.snapshot_hash,
            )
            .update(
                applied_snapshot_revision=snapshot.snapshot_revision,
                applied_snapshot_hash=snapshot.snapshot_hash,
                health_state=VPNNodeHealthState.READY,
                last_health_at=now,
                last_error_code="",
                updated_at=now,
            )
        )
        if updated != 1:
            return False
        included_access_ids = tuple(access.access_id for access in snapshot.accesses)
        VPNAccessNodeApply.objects.active().filter(node_id=node.pk).exclude(
            access_id__in=included_access_ids
        ).update(
            is_active=False,
            applied_revision=None,
            status=VPNApplyStatus.PENDING,
            last_attempt_at=now,
            last_error_code="",
            updated_at=now,
        )
        for access in snapshot.accesses:
            VPNAccessNodeApply.objects.active().filter(
                access_id=access.access_id,
                node_id=node.pk,
                desired_revision=access.access_revision,
            ).update(
                applied_revision=access.access_revision,
                status=VPNApplyStatus.APPLIED,
                last_attempt_at=now,
                last_error_code="",
                updated_at=now,
            )
        return True


def mark_vpn_node_snapshot_failed(
    *,
    node: VPNNode,
    snapshot: VPNExactSnapshotDTO,
    state: str,
    code: str,
    now: datetime,
) -> bool:
    changed = (
        VPNNode.objects.active()
        .filter(
            pk=node.pk,
            desired_snapshot_revision=snapshot.snapshot_revision,
            desired_snapshot_hash=snapshot.snapshot_hash,
        )
        .exclude(Q(health_state=state) & Q(last_error_code=code))
        .update(
            health_state=state,
            last_health_at=now,
            last_error_code=code,
            updated_at=now,
        )
    )
    if changed:
        VPNAccessNodeApply.objects.active().filter(
            node_id=node.pk,
            status=VPNApplyStatus.PENDING,
        ).update(
            status=VPNApplyStatus.FAILED,
            last_attempt_at=now,
            last_error_code=code,
            updated_at=now,
        )
    return changed == 1


def record_vpn_node_health(*, node: VPNNode, health: VPNAgentHealthDTO) -> None:
    now = timezone.now()
    fields: dict[str, object] = {
        "last_health_at": now,
        "updated_at": now,
    }
    exact = (
        health.readiness == "READY"
        and health.applied_snapshot_revision == node.desired_snapshot_revision
        and health.applied_snapshot_hash == node.desired_snapshot_hash
        and node.desired_snapshot_revision > 0
    )
    if health.readiness == "RECOVERY_READY" or not exact:
        fields["health_state"] = VPNNodeHealthState.SYNCING
    elif node.health_state == VPNNodeHealthState.READY:
        fields["last_error_code"] = ""
    VPNNode.objects.active().filter(pk=node.pk).update(**fields)


def record_vpn_node_health_failure(
    *, node: VPNNode, error: VPNAgentTransportError
) -> None:
    state = (
        VPNNodeHealthState.INCOMPATIBLE
        if isinstance(error, VPNAgentContractError)
        else VPNNodeHealthState.UNHEALTHY
    )
    now = timezone.now()
    VPNNode.objects.active().filter(pk=node.pk).update(
        health_state=state,
        last_health_at=now,
        last_error_code=error.error_code,
        updated_at=now,
    )


def record_vpn_node_unexpected_failure(*, node: VPNNode, error_code: str) -> None:
    """Persist a bounded code without retaining the raw exception."""
    now = timezone.now()
    VPNNode.objects.active().filter(pk=node.pk).update(
        health_state=VPNNodeHealthState.UNHEALTHY,
        last_error_code=error_code,
        updated_at=now,
    )


def get_access_node_applies(*, access: VPNAccess) -> QuerySet[VPNAccessNodeApply]:
    return (
        VPNAccessNodeApply.objects.active().filter(access=access).select_related("node")
    )


def get_vpn_access_for_delivery(*, access_id: int) -> VPNAccess | None:
    return (
        VPNAccess.objects.active().filter(pk=access_id).select_related("user").first()
    )


def has_eligible_exact_vpn_apply(*, access: VPNAccess) -> bool:
    """Return durable evidence that current desired credential is publishable."""
    return (
        VPNAccessNodeApply.objects.active()
        .filter(
            access=access,
            desired_revision=access.desired_revision,
            applied_revision=access.desired_revision,
            status="applied",
            node__is_active=True,
            node__is_access_available=True,
            node__health_state=VPNNodeHealthState.READY,
            node__desired_snapshot_revision__gt=0,
            node__applied_snapshot_revision=F("node__desired_snapshot_revision"),
            node__applied_snapshot_hash=F("node__desired_snapshot_hash"),
        )
        .exclude(node__desired_snapshot_hash="")
        .exists()
    )


def publish_vpn_access_conditionally(*, access: VPNAccess) -> bool:
    """Publish current desired pair only while exact eligible evidence exists."""
    eligible_apply = (
        VPNAccessNodeApply.objects.active()
        .filter(
            access_id=OuterRef("pk"),
            desired_revision=OuterRef("desired_revision"),
            applied_revision=OuterRef("desired_revision"),
            status=VPNApplyStatus.APPLIED,
            node__is_active=True,
            node__is_access_available=True,
            node__health_state=VPNNodeHealthState.READY,
            node__desired_snapshot_revision__gt=0,
            node__applied_snapshot_revision=F("node__desired_snapshot_revision"),
            node__applied_snapshot_hash=F("node__desired_snapshot_hash"),
        )
        .exclude(node__desired_snapshot_hash="")
    )
    return (
        VPNAccess.objects.active()
        .annotate(has_eligible_apply=Exists(eligible_apply))
        .filter(
            pk=access.pk,
            state=VPNAccessState.PREPARING,
            state_revision=access.state_revision,
            desired_uuid=access.desired_uuid,
            desired_revision=access.desired_revision,
            has_eligible_apply=True,
        )
        .update(
            published_uuid=access.desired_uuid,
            published_revision=access.desired_revision,
            state=VPNAccessState.READY,
            state_revision=F("state_revision") + 1,
        )
        == 1
    )


def mark_vpn_ready_notification_sent(*, access_id: int, revision: int) -> bool:
    return (
        VPNAccess.objects.active()
        .filter(
            pk=access_id,
            state=VPNAccessState.READY,
            published_revision=revision,
            ready_notification_revision__lt=revision,
        )
        .update(ready_notification_revision=revision)
        == 1
    )


def get_pending_vpn_ready_notifications(*, limit: int = 100) -> QuerySet[VPNAccess]:
    """Return durable notification work; a failed enqueue remains selectable."""
    return (
        VPNAccess.objects.active()
        .filter(
            state=VPNAccessState.READY,
            published_revision__isnull=False,
            ready_notification_revision__lt=F("published_revision"),
        )
        .select_related("user")
        .order_by("pk")[:limit]
    )


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
