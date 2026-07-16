from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import final

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


_ALERT_RESOURCE_KINDS = frozenset({"fleet", "node", "receipt", "notification"})
_ALERT_ERROR_CODES = frozenset(
    {
        "agent_tls_failure",
        "agent_unauthorized",
        "incompatible_contract",
        "no_ready_node",
        "notification_failure",
        "revision_drift",
        "snapshot_too_large",
        "stale_receipt",
    }
)
_METRIC_NAMES = frozenset(
    {
        "vpn_auth_failures_current",
        "vpn_nodes_incompatible_current",
        "vpn_nodes_over_capacity_current",
        "vpn_nodes_revision_drift_current",
        "vpn_oldest_node_health_seconds",
        "vpn_oldest_unapplied_receipt_seconds",
        "vpn_pending_ready_notifications_current",
        "vpn_preparing_accesses_current",
        "vpn_ready_nodes_current",
        "vpn_readiness_latency_seconds",
        "vpn_receipt_apply_latency_seconds",
        "vpn_receipt_attempts_current",
        "vpn_receipt_lease_recovery_total",
        "vpn_receipts_applied_current",
        "vpn_receipts_processing_current",
        "vpn_receipts_received_current",
        "vpn_receipts_retry_current",
        "vpn_receipts_stale_current",
        "vpn_reconcile_delivery_failure_total",
        "vpn_reconcile_delivery_success_total",
        "vpn_reconcile_failures_current",
        "vpn_subscription_latency_observed_ms",
        "vpn_subscription_rate_limited_total",
        "vpn_subscription_requests_total",
        "vpn_tls_failures_current",
        "vpn_notification_delivery_failure_total",
        "vpn_notification_delivery_success_total",
    }
)


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class VPNMetric:
    name: str
    value: int

    def __post_init__(self) -> None:
        if self.name not in _METRIC_NAMES or self.value < 0:
            raise ValueError("Unsupported VPN metric")


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class VPNAlert:
    resource_kind: str
    resource_id: int
    error_code: str

    def __post_init__(self) -> None:
        if (
            self.resource_kind not in _ALERT_RESOURCE_KINDS
            or self.resource_id < 0
            or self.error_code not in _ALERT_ERROR_CODES
        ):
            raise ValueError("Unsupported VPN alert")

    @property
    def dedupe_key(self) -> str:
        return f"vpn-alert:{self.resource_kind}:{self.resource_id}:{self.error_code}"


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class VPNObservation:
    metrics: tuple[VPNMetric, ...]
    alerts: tuple[VPNAlert, ...]


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class SafeVPNAlertService:
    claim: Callable[..., bool]
    emit: Callable[[VPNAlert], None]
    dedupe_seconds: int

    def __call__(self, *, alert: VPNAlert) -> bool:
        if not self.claim(key=alert.dedupe_key, ttl_seconds=self.dedupe_seconds):
            return False
        self.emit(alert)
        return True


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class CollectVPNObservabilityService:
    get_observation: Callable[..., VPNObservation]
    emit_metric: Callable[[VPNMetric], None]
    emit_alert: Callable[..., bool]
    now: Callable[[], datetime]

    def __call__(self) -> VPNObservation:
        observation = self.get_observation(at=self.now())
        for metric in observation.metrics:
            try:
                self.emit_metric(metric)
            except Exception:
                logger.warning(
                    {
                        "event": "vpn_telemetry_sink_failure",
                        "sink": "metric",
                        "metric": metric.name,
                    }
                )
        for alert in observation.alerts:
            try:
                self.emit_alert(alert=alert)
            except Exception:
                logger.warning(
                    {
                        "event": "vpn_telemetry_sink_failure",
                        "sink": "alert",
                        "error_code": alert.error_code,
                    }
                )
        return observation


def emit_vpn_metric(metric: VPNMetric) -> None:
    logger.info(
        {
            "event": "vpn_metric",
            "metric": metric.name,
            "value": metric.value,
        }
    )


def emit_vpn_alert(alert: VPNAlert) -> None:
    logger.warning(
        {
            "event": "vpn_alert",
            "resource_kind": alert.resource_kind,
            "error_code": alert.error_code,
        }
    )


def get_vpn_observation(*, at: datetime) -> VPNObservation:
    from apps.payments.selectors import get_vpn_receipt_observability_summary
    from apps.vpn.selectors import get_vpn_runtime_observability_rows

    stale_seconds = settings.VPN_OBSERVABILITY_STALE_RECEIPT_SECONDS
    drift_seconds = settings.VPN_OBSERVABILITY_DRIFT_SECONDS
    auth_tls_seconds = settings.VPN_OBSERVABILITY_AUTH_TLS_SECONDS
    receipt_summary = get_vpn_receipt_observability_summary(
        at=at,
        stale_before=at - timedelta(seconds=stale_seconds),
    )
    runtime = get_vpn_runtime_observability_rows()

    oldest_unapplied_at = receipt_summary["oldest_unapplied_at"]
    oldest_unapplied = (
        max(0, int((at - oldest_unapplied_at).total_seconds()))
        if oldest_unapplied_at is not None
        else 0
    )
    apply_duration = receipt_summary["max_apply_duration"]
    apply_latency = max(0, int(apply_duration.total_seconds())) if apply_duration else 0
    readiness_duration = receipt_summary["max_readiness_duration"]
    readiness_latency = (
        max(0, int(readiness_duration.total_seconds())) if readiness_duration else 0
    )
    alerts: list[VPNAlert] = [
        VPNAlert(
            resource_kind="receipt",
            resource_id=receipt_id,
            error_code="stale_receipt",
        )
        for receipt_id in receipt_summary["stale_receipt_ids"]
    ]

    ready_nodes = 0
    incompatible = 0
    overflow = 0
    drift = 0
    auth = 0
    tls = 0
    reconcile_failures = 0
    oldest_health = 0
    for row in runtime["nodes"]:
        node_id = row["id"]
        exact = (
            row["health_state"] == "ready"
            and row["data_plane_state"] == "serving_ready"
            and row["is_access_available"]
            and row["desired_snapshot_revision"] > 0
            and row["desired_snapshot_revision"] == row["applied_snapshot_revision"]
            and row["desired_snapshot_hash"] != ""
            and row["desired_snapshot_hash"] == row["applied_snapshot_hash"]
        )
        ready_nodes += int(exact)
        incompatible += int(row["health_state"] == "incompatible")
        overflow += int(row["health_state"] == "over_capacity")
        mismatch = (
            row["desired_snapshot_revision"] != row["applied_snapshot_revision"]
            or row["desired_snapshot_hash"] != row["applied_snapshot_hash"]
        )
        health_age = None
        if row["last_health_at"] is not None:
            health_age = max(0, int((at - row["last_health_at"]).total_seconds()))
            oldest_health = max(oldest_health, health_age)
        drift_started_at = row["revision_drift_started_at"]
        prolonged = (
            drift_started_at is not None
            and (at - drift_started_at).total_seconds() >= drift_seconds
        )
        drift += int(mismatch)
        reconcile_failures += int(bool(row["last_error_code"]))
        if row["health_state"] == "incompatible":
            alerts.append(
                VPNAlert(
                    resource_kind="node",
                    resource_id=node_id,
                    error_code="incompatible_contract",
                )
            )
        if row["health_state"] == "over_capacity":
            alerts.append(
                VPNAlert(
                    resource_kind="node",
                    resource_id=node_id,
                    error_code="snapshot_too_large",
                )
            )
        if mismatch and prolonged:
            alerts.append(
                VPNAlert(
                    resource_kind="node",
                    resource_id=node_id,
                    error_code="revision_drift",
                )
            )
        error_started_at = row["last_error_started_at"]
        persistent_transport_failure = (
            error_started_at is not None
            and (at - error_started_at).total_seconds() >= auth_tls_seconds
        )
        if row["last_error_code"] == "agent_unauthorized":
            auth += 1
            if persistent_transport_failure:
                alerts.append(
                    VPNAlert(
                        resource_kind="node",
                        resource_id=node_id,
                        error_code="agent_unauthorized",
                    )
                )
        if row["last_error_code"] == "agent_tls_failure":
            tls += 1
            if persistent_transport_failure:
                alerts.append(
                    VPNAlert(
                        resource_kind="node",
                        resource_id=node_id,
                        error_code="agent_tls_failure",
                    )
                )

    if ready_nodes == 0:
        alerts.append(
            VPNAlert(resource_kind="fleet", resource_id=0, error_code="no_ready_node")
        )

    metrics = (
        VPNMetric(
            name="vpn_receipts_received_current",
            value=receipt_summary["received_count"],
        ),
        VPNMetric(
            name="vpn_receipts_processing_current",
            value=receipt_summary["processing_count"],
        ),
        VPNMetric(
            name="vpn_receipts_retry_current", value=receipt_summary["retry_count"]
        ),
        VPNMetric(
            name="vpn_receipts_applied_current", value=receipt_summary["applied_count"]
        ),
        VPNMetric(
            name="vpn_receipt_attempts_current", value=receipt_summary["attempts_sum"]
        ),
        VPNMetric(
            name="vpn_receipts_stale_current", value=receipt_summary["stale_count"]
        ),
        VPNMetric(name="vpn_oldest_unapplied_receipt_seconds", value=oldest_unapplied),
        VPNMetric(name="vpn_receipt_apply_latency_seconds", value=apply_latency),
        VPNMetric(name="vpn_readiness_latency_seconds", value=readiness_latency),
        VPNMetric(
            name="vpn_preparing_accesses_current", value=runtime["preparing_accesses"]
        ),
        VPNMetric(
            name="vpn_pending_ready_notifications_current",
            value=runtime["pending_notifications"],
        ),
        VPNMetric(name="vpn_ready_nodes_current", value=ready_nodes),
        VPNMetric(name="vpn_nodes_incompatible_current", value=incompatible),
        VPNMetric(name="vpn_nodes_over_capacity_current", value=overflow),
        VPNMetric(name="vpn_nodes_revision_drift_current", value=drift),
        VPNMetric(name="vpn_auth_failures_current", value=auth),
        VPNMetric(name="vpn_tls_failures_current", value=tls),
        VPNMetric(name="vpn_reconcile_failures_current", value=reconcile_failures),
        VPNMetric(name="vpn_oldest_node_health_seconds", value=oldest_health),
    )
    return VPNObservation(metrics=metrics, alerts=tuple(alerts))


def get_safe_vpn_alert_service() -> SafeVPNAlertService:
    from apps.vpn.infra import get_vpn_alert_dedupe

    return SafeVPNAlertService(
        claim=get_vpn_alert_dedupe(),
        emit=emit_vpn_alert,
        dedupe_seconds=settings.VPN_OBSERVABILITY_ALERT_DEDUPE_SECONDS,
    )


def get_collect_vpn_observability_service() -> CollectVPNObservabilityService:
    return CollectVPNObservabilityService(
        get_observation=get_vpn_observation,
        emit_metric=emit_vpn_metric,
        emit_alert=get_safe_vpn_alert_service(),
        now=timezone.now,
    )


__all__ = [
    "CollectVPNObservabilityService",
    "SafeVPNAlertService",
    "VPNAlert",
    "VPNMetric",
    "VPNObservation",
    "emit_vpn_alert",
    "emit_vpn_metric",
    "get_collect_vpn_observability_service",
    "get_safe_vpn_alert_service",
    "get_vpn_observation",
]
