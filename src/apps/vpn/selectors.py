from __future__ import annotations

from datetime import datetime
from uuid import UUID

from django.db import transaction
from django.db.models import Case, DateTimeField, Exists, F, OuterRef, Q, QuerySet, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.vpn.dtos import (
    VPNAgentHealthDTO,
    VPNDesiredAccessDTO,
    VPNExactSnapshotDTO,
)
from apps.vpn.enums import (
    VPNAccessState,
    VPNApplyStatus,
    VPNDataPlaneState,
    VPNNodeHealthState,
)
from apps.vpn.exceptions import VPNAgentContractError, VPNAgentTransportError
from apps.vpn.models import (
    VPNAccess,
    VPNAccessNodeApply,
    VPNAccessNodeRevisionEvidence,
    VPNNode,
    VPNPurchase,
)


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


def get_subscription_nodes(*, access: VPNAccess) -> QuerySet[VPNNode]:
    """Return ordered nodes with exact evidence for the published credential."""
    if access.published_revision is None:
        return VPNNode.objects.none()
    revision_history = VPNAccessNodeRevisionEvidence.objects.filter(
        node_id=OuterRef("pk"),
        access=access,
        revision=access.published_revision,
    )
    return (
        VPNNode.objects.active()
        .annotate(has_published_history=Exists(revision_history))
        .filter(
            Q(
                revision_evidences__is_active=True,
                revision_evidences__is_serving=True,
                revision_evidences__access=access,
                revision_evidences__revision=access.published_revision,
                revision_evidences__applied_revision=access.published_revision,
                revision_evidences__status=VPNApplyStatus.APPLIED,
            )
            | Q(
                has_published_history=False,
                access_applies__is_active=True,
                access_applies__access=access,
                access_applies__desired_revision=access.published_revision,
                access_applies__applied_revision=access.published_revision,
                access_applies__status=VPNApplyStatus.APPLIED,
            ),
            is_access_available=True,
            data_plane_state=VPNDataPlaneState.SERVING_READY,
        )
        .distinct()
        .order_by("number")
    )


def stage_vpn_access_reissue(
    *, access: VPNAccess, new_uuid: UUID, now: datetime
) -> bool:
    return (
        VPNAccess.objects.active()
        .filter(
            pk=access.pk,
            state=VPNAccessState.READY,
            state_revision=access.state_revision,
            desired_revision=access.desired_revision,
            published_revision=access.desired_revision,
            expired_at__gt=now,
            disabled_at__isnull=True,
        )
        .update(
            desired_uuid=new_uuid,
            desired_revision=F("desired_revision") + 1,
            state=VPNAccessState.PREPARING,
            state_revision=F("state_revision") + 1,
            updated_at=now,
        )
        == 1
    )


def get_due_vpn_accesses(*, now: datetime, limit: int = 500) -> QuerySet[VPNAccess]:
    return VPNAccess.objects.active().filter(
        expired_at__lte=now,
        state__in=(VPNAccessState.PREPARING, VPNAccessState.READY),
    ).order_by("pk")[:limit]


def expire_vpn_access_conditionally(*, access: VPNAccess, now: datetime) -> bool:
    return (
        VPNAccess.objects.active()
        .filter(
            pk=access.pk,
            state_revision=access.state_revision,
            expired_at__lte=now,
            state__in=(VPNAccessState.PREPARING, VPNAccessState.READY),
        )
        .update(
            state=VPNAccessState.EXPIRED,
            state_revision=F("state_revision") + 1,
            updated_at=now,
        )
        == 1
    )


def deactivate_vpn_refund_conditionally(
    *, access: VPNAccess, actor_id: int, reason: str, now: datetime
) -> bool:
    return (
        VPNAccess.objects.active()
        .filter(
            pk=access.pk,
            state_revision=access.state_revision,
            disabled_at__isnull=True,
        )
        .exclude(state=VPNAccessState.DISABLED_REFUND)
        .update(
            state=VPNAccessState.DISABLED_REFUND,
            state_revision=F("state_revision") + 1,
            disabled_at=now,
            disabled_by_id=actor_id,
            disabled_reason=reason,
            updated_at=now,
        )
        == 1
    )


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
            revision_drift_started_at=Coalesce(
                "revision_drift_started_at", Value(now)
            ),
            last_error_code="",
            last_error_started_at=None,
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
        history = VPNAccessNodeRevisionEvidence.objects.filter(
            access_id=access.access_id,
            node_id=node.pk,
            revision=access.access_revision,
        )
        already_serving_exact = history.filter(
            is_active=True,
            is_serving=True,
            status=VPNApplyStatus.APPLIED,
            applied_revision=access.access_revision,
        ).exists()
        if already_serving_exact:
            history.update(last_attempt_at=now, updated_at=now)
        else:
            VPNAccessNodeRevisionEvidence.objects.update_or_create(
                access_id=access.access_id,
                node_id=node.pk,
                revision=access.access_revision,
                defaults={
                    "applied_revision": None,
                    "status": VPNApplyStatus.PENDING,
                    "is_serving": False,
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
                last_error_started_at=None,
                revision_drift_started_at=None,
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
        VPNAccessNodeRevisionEvidence.objects.filter(node_id=node.pk).exclude(
            access_id__in=included_access_ids
        ).update(is_active=False, is_serving=False, updated_at=now)
        for access in snapshot.accesses:
            is_current_published = VPNAccess.objects.active().filter(
                pk=access.access_id,
                state=VPNAccessState.READY,
                published_revision=access.access_revision,
            ).exists()
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
            VPNAccessNodeRevisionEvidence.objects.active().filter(
                access_id=access.access_id,
                node_id=node.pk,
                revision=access.access_revision,
            ).update(
                applied_revision=access.access_revision,
                status=VPNApplyStatus.APPLIED,
                is_serving=is_current_published,
                last_attempt_at=now,
                last_error_code="",
                updated_at=now,
            )
        VPNNode.objects.active().filter(pk=node.pk).update(
            data_plane_state=VPNDataPlaneState.SERVING_READY,
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
            last_error_started_at=Case(
                When(
                    last_error_code=code,
                    then=Coalesce("last_error_started_at", Value(now)),
                ),
                default=Value(now),
                output_field=DateTimeField(),
            ),
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
        VPNAccessNodeRevisionEvidence.objects.active().filter(
            node_id=node.pk,
            revision__in=tuple(access.access_revision for access in snapshot.accesses),
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
        "last_error_code": Case(
            When(
                last_error_code__in=("agent_unauthorized", "agent_tls_failure"),
                then=Value(""),
            ),
            default=F("last_error_code"),
        ),
        "last_error_started_at": Case(
            When(
                last_error_code__in=("agent_unauthorized", "agent_tls_failure"),
                then=Value(None),
            ),
            default=F("last_error_started_at"),
            output_field=DateTimeField(),
        ),
        "updated_at": now,
    }
    exact = (
        health.readiness == "READY"
        and health.applied_snapshot_revision == node.desired_snapshot_revision
        and health.applied_snapshot_hash == node.desired_snapshot_hash
        and node.desired_snapshot_revision > 0
    )
    confirms_serving_snapshot = (
        health.readiness == "READY"
        and node.data_plane_state == VPNDataPlaneState.SERVING_READY
        and health.applied_snapshot_revision == node.applied_snapshot_revision
        and health.applied_snapshot_hash == node.applied_snapshot_hash
        and node.applied_snapshot_revision > 0
    )
    if health.readiness == "RECOVERY_READY" or not exact:
        fields["health_state"] = VPNNodeHealthState.SYNCING
        if not confirms_serving_snapshot:
            fields["data_plane_state"] = VPNDataPlaneState.UNAVAILABLE
        fields["revision_drift_started_at"] = Coalesce(
            "revision_drift_started_at", Value(now)
        )
    else:
        fields["revision_drift_started_at"] = None
        if node.health_state == VPNNodeHealthState.READY:
            fields["last_error_code"] = ""
            fields["last_error_started_at"] = None
    with transaction.atomic():
        VPNNode.objects.active().filter(pk=node.pk).update(**fields)
        if (health.readiness == "RECOVERY_READY" or not exact) and not (
            confirms_serving_snapshot
        ):
            VPNAccessNodeRevisionEvidence.objects.active().filter(
                node_id=node.pk, is_serving=True
            ).update(is_serving=False, updated_at=now)


def record_vpn_node_health_failure(
    *, node: VPNNode, error: VPNAgentTransportError
) -> None:
    state = (
        VPNNodeHealthState.INCOMPATIBLE
        if isinstance(error, VPNAgentContractError)
        else VPNNodeHealthState.UNHEALTHY
    )
    now = timezone.now()
    with transaction.atomic():
        VPNNode.objects.active().filter(pk=node.pk).update(
            health_state=state,
            data_plane_state=VPNDataPlaneState.UNAVAILABLE,
            last_health_at=now,
            last_error_code=error.error_code,
            last_error_started_at=Case(
                When(
                    last_error_code=error.error_code,
                    then=Coalesce("last_error_started_at", Value(now)),
                ),
                default=Value(now),
                output_field=DateTimeField(),
            ),
            updated_at=now,
        )
        VPNAccessNodeRevisionEvidence.objects.active().filter(
            node_id=node.pk, is_serving=True
        ).update(is_serving=False, updated_at=now)


def record_vpn_node_unexpected_failure(*, node: VPNNode, error_code: str) -> None:
    """Persist a bounded code without retaining the raw exception."""
    now = timezone.now()
    with transaction.atomic():
        VPNNode.objects.active().filter(pk=node.pk).update(
            health_state=VPNNodeHealthState.UNHEALTHY,
            data_plane_state=VPNDataPlaneState.UNAVAILABLE,
            last_error_code=error_code,
            last_error_started_at=Case(
                When(
                    last_error_code=error_code,
                    then=Coalesce("last_error_started_at", Value(now)),
                ),
                default=Value(now),
                output_field=DateTimeField(),
            ),
            updated_at=now,
        )
        VPNAccessNodeRevisionEvidence.objects.active().filter(
            node_id=node.pk, is_serving=True
        ).update(is_serving=False, updated_at=now)


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
    history = (
        VPNAccessNodeRevisionEvidence.objects.active()
        .filter(
            access=access,
            revision=access.desired_revision,
            applied_revision=access.desired_revision,
            status="applied",
            node__is_active=True,
            node__is_access_available=True,
            node__data_plane_state=VPNDataPlaneState.SERVING_READY,
            node__health_state=VPNNodeHealthState.READY,
            node__desired_snapshot_revision__gt=0,
            node__applied_snapshot_revision=F("node__desired_snapshot_revision"),
            node__applied_snapshot_hash=F("node__desired_snapshot_hash"),
        )
        .exclude(node__desired_snapshot_hash="")
        .exists()
    )
    if history:
        return True
    if VPNAccessNodeRevisionEvidence.objects.filter(
        access=access, revision=access.desired_revision
    ).exists():
        return False
    return (
        VPNAccessNodeApply.objects.active()
        .filter(
            access=access,
            desired_revision=access.desired_revision,
            applied_revision=access.desired_revision,
            status=VPNApplyStatus.APPLIED,
            node__is_active=True,
            node__is_access_available=True,
            node__data_plane_state=VPNDataPlaneState.SERVING_READY,
            node__health_state=VPNNodeHealthState.READY,
            node__desired_snapshot_revision__gt=0,
            node__applied_snapshot_revision=F("node__desired_snapshot_revision"),
            node__applied_snapshot_hash=F("node__desired_snapshot_hash"),
        )
        .exclude(node__desired_snapshot_hash="")
        .exists()
    )


def publish_vpn_access_conditionally(
    *, access: VPNAccess, now: datetime | None = None
) -> bool:
    """Publish current desired pair only while exact eligible evidence exists."""
    eligible_apply = (
        VPNAccessNodeRevisionEvidence.objects.active()
        .filter(
            access_id=OuterRef("pk"),
            revision=OuterRef("desired_revision"),
            applied_revision=OuterRef("desired_revision"),
            status=VPNApplyStatus.APPLIED,
            node__is_active=True,
            node__is_access_available=True,
            node__data_plane_state=VPNDataPlaneState.SERVING_READY,
            node__health_state=VPNNodeHealthState.READY,
            node__desired_snapshot_revision__gt=0,
            node__applied_snapshot_revision=F("node__desired_snapshot_revision"),
            node__applied_snapshot_hash=F("node__desired_snapshot_hash"),
        )
        .exclude(node__desired_snapshot_hash="")
    )
    any_history = VPNAccessNodeRevisionEvidence.objects.filter(
        access_id=OuterRef("pk"), revision=OuterRef("desired_revision")
    )
    eligible_legacy = (
        VPNAccessNodeApply.objects.active()
        .filter(
            access_id=OuterRef("pk"),
            desired_revision=OuterRef("desired_revision"),
            applied_revision=OuterRef("desired_revision"),
            status=VPNApplyStatus.APPLIED,
            node__is_active=True,
            node__is_access_available=True,
            node__data_plane_state=VPNDataPlaneState.SERVING_READY,
            node__health_state=VPNNodeHealthState.READY,
            node__desired_snapshot_revision__gt=0,
            node__applied_snapshot_revision=F("node__desired_snapshot_revision"),
            node__applied_snapshot_hash=F("node__desired_snapshot_hash"),
        )
        .exclude(node__desired_snapshot_hash="")
    )
    effective_now = now or timezone.now()
    return (
        VPNAccess.objects.active()
        .annotate(
            has_eligible_apply=Exists(eligible_apply),
            has_revision_history=Exists(any_history),
            has_eligible_legacy=Exists(eligible_legacy),
        )
        .filter(
            pk=access.pk,
            state=VPNAccessState.PREPARING,
            state_revision=access.state_revision,
            desired_uuid=access.desired_uuid,
            desired_revision=access.desired_revision,
        )
        .filter(
            Q(has_eligible_apply=True)
            | Q(has_revision_history=False, has_eligible_legacy=True)
        )
        .update(
            published_uuid=access.desired_uuid,
            published_revision=access.desired_revision,
            state=VPNAccessState.READY,
            state_revision=F("state_revision") + 1,
            first_ready_at=Coalesce("first_ready_at", Value(effective_now)),
        )
        == 1
    )


def deactivate_superseded_vpn_applies(*, access: VPNAccess) -> None:
    now = timezone.now()
    VPNAccessNodeRevisionEvidence.objects.active().filter(access=access).exclude(
        revision=access.desired_revision
    ).update(is_serving=False, updated_at=now)
    VPNAccessNodeRevisionEvidence.objects.active().filter(
        access=access,
        revision=access.desired_revision,
        status=VPNApplyStatus.APPLIED,
        applied_revision=access.desired_revision,
    ).update(is_serving=True, updated_at=now)


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


def get_vpn_runtime_observability_rows() -> dict[str, object]:
    """Return only bounded node/access fields required for operational metrics."""
    nodes = list(
        VPNNode.objects.active()
        .values(
            "id",
            "health_state",
            "data_plane_state",
            "is_access_available",
            "desired_snapshot_revision",
            "desired_snapshot_hash",
            "applied_snapshot_revision",
            "applied_snapshot_hash",
            "last_health_at",
            "last_error_code",
            "last_error_started_at",
            "revision_drift_started_at",
        )
        .order_by("pk")
    )
    preparing_accesses = (
        VPNAccess.objects.active().filter(state=VPNAccessState.PREPARING).count()
    )
    pending_notifications = (
        VPNAccess.objects.active()
        .filter(
            state=VPNAccessState.READY,
            published_revision__isnull=False,
            ready_notification_revision__lt=F("published_revision"),
        )
        .count()
    )
    return {
        "nodes": nodes,
        "preparing_accesses": preparing_accesses,
        "pending_notifications": pending_notifications,
    }


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
