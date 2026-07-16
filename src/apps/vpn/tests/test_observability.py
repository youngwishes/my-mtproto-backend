from __future__ import annotations

from datetime import timedelta
import logging
from pathlib import Path
from unittest import mock
import uuid

from django.test import SimpleTestCase, TestCase, override_settings
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.payments.enums import PaymentReceiptStatusEnum
from apps.payments.enums import ProductCodeEnum
from apps.payments.tests.factories import (
    PaymentFactory,
    PaymentIntentFactory,
    PaymentReceiptFactory,
    ProductFactory,
)
from apps.payments.selectors import get_vpn_receipt_observability_summary
from apps.vpn.enums import VPNAccessState, VPNDataPlaneState, VPNNodeHealthState
from apps.vpn.dtos import VPNAgentHealthDTO
from apps.vpn.exceptions import VPNAgentAuthenticationError, VPNAgentTLSFailure
from apps.vpn.observability import (
    CollectVPNObservabilityService,
    SafeVPNAlertService,
    VPNAlert,
    VPNMetric,
    VPNObservation,
    get_vpn_observation,
)
from apps.vpn.tests.factories import (
    VPNAccessFactory,
    VPNNodeFactory,
    VPNPurchaseFactory,
)
from apps.vpn.selectors import record_vpn_node_health, record_vpn_node_health_failure


class SafeVPNAlertServiceTests(SimpleTestCase):
    def test_repeated_alert_uses_stable_dedupe_key_and_emits_once(self) -> None:
        claimed: set[str] = set()
        emitted: list[VPNAlert] = []
        service = SafeVPNAlertService(
            claim=lambda *, key, ttl_seconds: not (key in claimed or claimed.add(key)),
            emit=emitted.append,
            dedupe_seconds=3600,
        )
        alert = VPNAlert(
            resource_kind="node",
            resource_id=41,
            error_code="revision_drift",
        )

        self.assertTrue(service(alert=alert))
        self.assertFalse(service(alert=alert))

        self.assertEqual(
            claimed,
            {"vpn-alert:node:41:revision_drift"},
        )
        self.assertEqual(emitted, [alert])

    def test_alert_contract_rejects_unbounded_or_secret_bearing_fields(self) -> None:
        service = SafeVPNAlertService(
            claim=lambda **_: True,
            emit=mock.Mock(),
            dedupe_seconds=3600,
        )

        with self.assertRaises(ValueError):
            service(
                alert=VPNAlert(
                    resource_kind="node",
                    resource_id=1,
                    error_code="https://example.test/sub/token?payload=secret",
                )
            )


class CollectVPNObservabilityServiceTests(SimpleTestCase):
    def test_emits_each_metric_and_actionable_alert(self) -> None:
        metrics = (
            VPNMetric(name="vpn_ready_nodes_current", value=0),
            VPNMetric(name="vpn_receipts_stale_current", value=1),
        )
        alerts = (
            VPNAlert(resource_kind="fleet", resource_id=0, error_code="no_ready_node"),
        )
        emitted_metrics: list[VPNMetric] = []
        emitted_alerts: list[VPNAlert] = []
        service = CollectVPNObservabilityService(
            get_observation=lambda *, at: VPNObservation(
                metrics=metrics, alerts=alerts
            ),
            emit_metric=emitted_metrics.append,
            emit_alert=lambda *, alert: emitted_alerts.append(alert) or True,
            now=lambda: timezone.now(),
        )

        result = service()

        self.assertEqual(result, VPNObservation(metrics=metrics, alerts=alerts))
        self.assertEqual(emitted_metrics, list(metrics))
        self.assertEqual(emitted_alerts, list(alerts))

    def test_telemetry_sink_failure_does_not_break_collection(self) -> None:
        observation = VPNObservation(
            metrics=(VPNMetric(name="vpn_ready_nodes_current", value=1),),
            alerts=(
                VPNAlert(
                    resource_kind="node",
                    resource_id=1,
                    error_code="revision_drift",
                ),
            ),
        )
        service = CollectVPNObservabilityService(
            get_observation=lambda *, at: observation,
            emit_metric=mock.Mock(side_effect=OSError("sink unavailable")),
            emit_alert=mock.Mock(side_effect=OSError("redis unavailable")),
            now=timezone.now,
        )

        with self.assertLogs("apps.vpn.observability", level=logging.WARNING):
            result = service()

        self.assertEqual(result, observation)


@override_settings(
    VPN_OBSERVABILITY_STALE_RECEIPT_SECONDS=300,
    VPN_OBSERVABILITY_DRIFT_SECONDS=900,
    VPN_OBSERVABILITY_AUTH_TLS_SECONDS=900,
)
class VPNObservationDatabaseTests(TestCase):
    def test_receipt_selector_uses_sql_aggregates_and_bounds_alert_candidates(
        self,
    ) -> None:
        now = timezone.now()
        product = ProductFactory(code=ProductCodeEnum.VLESS_30D)
        for _ in range(105):
            receipt = PaymentReceiptFactory(
                status=PaymentReceiptStatusEnum.RECEIVED,
                intent=PaymentIntentFactory(product=product),
            )
            type(receipt).objects.filter(pk=receipt.pk)._safe_update(
                accepted_at=now - timedelta(minutes=10)
            )

        with CaptureQueriesContext(connection) as queries:
            summary = get_vpn_receipt_observability_summary(
                at=now,
                stale_before=now - timedelta(minutes=5),
                alert_limit=100,
            )

        self.assertEqual(len(queries), 2)
        self.assertEqual(summary["received_count"], 105)
        self.assertEqual(summary["stale_count"], 105)
        self.assertEqual(len(summary["stale_receipt_ids"]), 100)

    def test_transition_latency_metrics_ignore_later_model_updates(self) -> None:
        now = timezone.now()
        accepted_at = now - timedelta(minutes=10)
        applied_at = now - timedelta(minutes=7)
        first_ready_at = now - timedelta(minutes=2)
        product = ProductFactory(code=ProductCodeEnum.VLESS_30D)
        receipt = PaymentReceiptFactory(
            status=PaymentReceiptStatusEnum.RECEIVED,
            intent=PaymentIntentFactory(product=product),
        )
        payment = PaymentFactory(
            user=receipt.user,
            product=product,
            provider=receipt.provider,
            charge_id=receipt.charge_id,
        )
        type(receipt).objects.filter(pk=receipt.pk)._safe_update(
            status=PaymentReceiptStatusEnum.APPLIED,
            payment=payment,
            accepted_at=accepted_at,
            applied_at=applied_at,
            ready_at=first_ready_at,
            updated_at=now,
        )
        access = VPNAccessFactory(
            state=VPNAccessState.PREPARING,
            first_ready_at=first_ready_at,
        )
        VPNPurchaseFactory(payment=payment, access=access)
        type(access).objects.filter(pk=access.pk).update(
            updated_at=now + timedelta(hours=2)
        )

        observation = get_vpn_observation(at=now)
        values = {metric.name: metric.value for metric in observation.metrics}

        self.assertEqual(values["vpn_receipt_apply_latency_seconds"], 180)
        self.assertEqual(values["vpn_readiness_latency_seconds"], 300)

    def test_continuous_transport_failure_preserves_onset_and_recovery_resets_it(
        self,
    ) -> None:
        first = timezone.now() - timedelta(minutes=20)
        second = first + timedelta(minutes=5)
        recovered = second + timedelta(minutes=5)
        node = VPNNodeFactory(
            health_state=VPNNodeHealthState.READY,
            desired_snapshot_revision=1,
            desired_snapshot_hash="a" * 64,
            applied_snapshot_revision=1,
            applied_snapshot_hash="a" * 64,
        )

        with mock.patch("apps.vpn.selectors.timezone.now", return_value=first):
            record_vpn_node_health_failure(
                node=node,
                error=VPNAgentAuthenticationError(node.pk),
            )
        node.refresh_from_db()
        self.assertEqual(node.last_error_started_at, first)

        with mock.patch("apps.vpn.selectors.timezone.now", return_value=second):
            record_vpn_node_health_failure(
                node=node,
                error=VPNAgentAuthenticationError(node.pk),
            )
        node.refresh_from_db()
        self.assertEqual(node.last_error_started_at, first)

        exact_health = VPNAgentHealthDTO(
            contract_version="v1",
            schema_version="1.0",
            agent_sha="a" * 40,
            xray_version="1",
            xray_image_digest=f"sha256:{'b' * 64}",
            readiness="READY",
            applied_snapshot_revision=1,
            applied_snapshot_hash="a" * 64,
        )
        with mock.patch("apps.vpn.selectors.timezone.now", return_value=recovered):
            record_vpn_node_health(node=node, health=exact_health)
        node.refresh_from_db()
        self.assertIsNone(node.last_error_started_at)
        self.assertEqual(node.last_error_code, "")

    def test_transport_error_code_transition_starts_a_new_onset(self) -> None:
        first = timezone.now() - timedelta(minutes=10)
        second = first + timedelta(minutes=5)
        node = VPNNodeFactory()
        with mock.patch("apps.vpn.selectors.timezone.now", return_value=first):
            record_vpn_node_health_failure(
                node=node,
                error=VPNAgentAuthenticationError(node.pk),
            )
        node.refresh_from_db()
        with mock.patch("apps.vpn.selectors.timezone.now", return_value=second):
            record_vpn_node_health_failure(
                node=node,
                error=VPNAgentTLSFailure(node.pk),
            )
        node.refresh_from_db()

        self.assertEqual(node.last_error_started_at, second)

    def test_unreconciled_desired_health_preserves_drift_onset(
        self,
    ) -> None:
        first = timezone.now() - timedelta(minutes=20)
        second = first + timedelta(minutes=5)
        recovered = second + timedelta(minutes=5)
        node = VPNNodeFactory(
            desired_snapshot_revision=2,
            desired_snapshot_hash="b" * 64,
            applied_snapshot_revision=1,
            applied_snapshot_hash="a" * 64,
        )
        drift_health = VPNAgentHealthDTO(
            contract_version="v1",
            schema_version="1.0",
            agent_sha="a" * 40,
            xray_version="1",
            xray_image_digest=f"sha256:{'b' * 64}",
            readiness="READY",
            applied_snapshot_revision=1,
            applied_snapshot_hash="a" * 64,
        )
        with mock.patch("apps.vpn.selectors.timezone.now", return_value=first):
            record_vpn_node_health(node=node, health=drift_health)
        node.refresh_from_db()
        self.assertEqual(node.revision_drift_started_at, first)

        with mock.patch("apps.vpn.selectors.timezone.now", return_value=second):
            record_vpn_node_health(node=node, health=drift_health)
        node.refresh_from_db()
        self.assertEqual(node.revision_drift_started_at, first)

        exact_health = VPNAgentHealthDTO(
            contract_version="v1",
            schema_version="1.0",
            agent_sha="a" * 40,
            xray_version="1",
            xray_image_digest=f"sha256:{'b' * 64}",
            readiness="READY",
            applied_snapshot_revision=2,
            applied_snapshot_hash="b" * 64,
        )
        with mock.patch("apps.vpn.selectors.timezone.now", return_value=recovered):
            record_vpn_node_health(node=node, health=exact_health)
        node.refresh_from_db()
        self.assertEqual(node.revision_drift_started_at, first)

    def test_snapshot_covers_receipt_readiness_node_and_notification_metrics(
        self,
    ) -> None:
        now = timezone.now()
        product = ProductFactory(code=ProductCodeEnum.VLESS_30D)
        stale = PaymentReceiptFactory(
            status=PaymentReceiptStatusEnum.RECEIVED,
            intent=PaymentIntentFactory(product=product),
        )
        PaymentReceiptFactory(
            status=PaymentReceiptStatusEnum.RETRY,
            attempt_count=3,
            intent=PaymentIntentFactory(product=product),
            next_attempt_at=now - timedelta(seconds=1),
        )
        applied = PaymentReceiptFactory(
            status=PaymentReceiptStatusEnum.RECEIVED,
            intent=PaymentIntentFactory(product=product),
        )
        applied_payment = PaymentFactory(
            user=applied.user,
            product=applied.product,
            provider=applied.provider,
            charge_id=applied.charge_id,
        )
        type(applied).objects.filter(pk=applied.pk)._safe_update(
            status=PaymentReceiptStatusEnum.APPLIED,
            payment=applied_payment,
        )
        type(stale).objects.filter(pk=stale.pk)._safe_update(
            accepted_at=now - timedelta(minutes=10)
        )
        VPNAccessFactory(state=VPNAccessState.PREPARING)
        credential = uuid.uuid4()
        VPNAccessFactory(
            state=VPNAccessState.READY,
            desired_uuid=credential,
            published_uuid=credential,
            published_revision=1,
        )
        ready = VPNNodeFactory(
            health_state=VPNNodeHealthState.READY,
            data_plane_state=VPNDataPlaneState.SERVING_READY,
            desired_snapshot_revision=1,
            desired_snapshot_hash="a" * 64,
            applied_snapshot_revision=1,
            applied_snapshot_hash="a" * 64,
        )
        self.assertIsNotNone(applied_payment.pk)
        self.assertIsNotNone(ready.pk)

        observation = get_vpn_observation(at=now)
        values = {metric.name: metric.value for metric in observation.metrics}

        self.assertEqual(values["vpn_receipts_received_current"], 1)
        self.assertEqual(values["vpn_receipts_retry_current"], 1)
        self.assertEqual(values["vpn_receipts_applied_current"], 1)
        self.assertEqual(values["vpn_receipt_attempts_current"], 3)
        self.assertEqual(values["vpn_receipts_stale_current"], 1)
        self.assertGreaterEqual(values["vpn_oldest_unapplied_receipt_seconds"], 600)
        self.assertEqual(values["vpn_preparing_accesses_current"], 1)
        self.assertEqual(values["vpn_ready_nodes_current"], 1)
        self.assertIn("vpn_pending_ready_notifications_current", values)

    def test_management_ready_but_non_serving_node_does_not_hide_fleet_alert(
        self,
    ) -> None:
        now = timezone.now()
        VPNNodeFactory(
            health_state=VPNNodeHealthState.READY,
            data_plane_state=VPNDataPlaneState.UNAVAILABLE,
            desired_snapshot_revision=1,
            desired_snapshot_hash="a" * 64,
            applied_snapshot_revision=1,
            applied_snapshot_hash="a" * 64,
        )

        observation = get_vpn_observation(at=now)
        values = {metric.name: metric.value for metric in observation.metrics}

        self.assertEqual(values["vpn_ready_nodes_current"], 0)
        self.assertIn(
            VPNAlert(resource_kind="fleet", resource_id=0, error_code="no_ready_node"),
            observation.alerts,
        )

    def test_preparing_access_is_not_reported_as_ready_latency(self) -> None:
        now = timezone.now()
        product = ProductFactory(code=ProductCodeEnum.VLESS_30D)
        receipt = PaymentReceiptFactory(
            status=PaymentReceiptStatusEnum.RECEIVED,
            intent=PaymentIntentFactory(product=product),
        )
        payment = PaymentFactory(
            user=receipt.user,
            product=product,
            provider=receipt.provider,
            charge_id=receipt.charge_id,
        )
        type(receipt).objects.filter(pk=receipt.pk)._safe_update(
            status=PaymentReceiptStatusEnum.APPLIED,
            payment=payment,
            accepted_at=now - timedelta(minutes=10),
        )
        VPNPurchaseFactory(
            payment=payment,
            access=VPNAccessFactory(state=VPNAccessState.PREPARING),
        )

        observation = get_vpn_observation(at=now)
        values = {metric.name: metric.value for metric in observation.metrics}

        self.assertEqual(values["vpn_readiness_latency_seconds"], 0)

    def test_alerts_cover_required_states_without_secret_values(self) -> None:
        now = timezone.now()
        product = ProductFactory(code=ProductCodeEnum.VLESS_30D)
        stale = PaymentReceiptFactory(
            status=PaymentReceiptStatusEnum.RECEIVED,
            intent=PaymentIntentFactory(product=product),
        )
        type(stale).objects.filter(pk=stale.pk)._safe_update(
            accepted_at=now - timedelta(minutes=10)
        )
        incompatible = VPNNodeFactory(
            health_state=VPNNodeHealthState.INCOMPATIBLE,
            last_error_code="incompatible_contract",
        )
        overflow = VPNNodeFactory(
            health_state=VPNNodeHealthState.OVER_CAPACITY,
            last_error_code="snapshot_too_large",
        )
        drift = VPNNodeFactory(
            health_state=VPNNodeHealthState.SYNCING,
            desired_snapshot_revision=2,
            desired_snapshot_hash="b" * 64,
            applied_snapshot_revision=1,
            applied_snapshot_hash="a" * 64,
            last_health_at=now - timedelta(minutes=20),
            revision_drift_started_at=now - timedelta(minutes=20),
        )
        auth = VPNNodeFactory(
            health_state=VPNNodeHealthState.UNHEALTHY,
            last_error_code="agent_unauthorized",
            last_health_at=now - timedelta(minutes=20),
            last_error_started_at=now - timedelta(minutes=20),
        )
        tls = VPNNodeFactory(
            health_state=VPNNodeHealthState.UNHEALTHY,
            last_error_code="agent_tls_failure",
            last_health_at=now - timedelta(minutes=20),
            last_error_started_at=now - timedelta(minutes=20),
        )

        observation = get_vpn_observation(at=now)
        identities = {
            (alert.resource_kind, alert.resource_id, alert.error_code)
            for alert in observation.alerts
        }

        self.assertIn(("fleet", 0, "no_ready_node"), identities)
        self.assertIn(("receipt", stale.pk, "stale_receipt"), identities)
        self.assertIn(("node", incompatible.pk, "incompatible_contract"), identities)
        self.assertIn(("node", overflow.pk, "snapshot_too_large"), identities)
        self.assertIn(("node", drift.pk, "revision_drift"), identities)
        self.assertIn(("node", auth.pk, "agent_unauthorized"), identities)
        self.assertIn(("node", tls.pk, "agent_tls_failure"), identities)
        rendered = repr(observation)
        for forbidden in (
            "subscription_token",
            "desired_uuid",
            "Authorization",
            "provider_data",
            "vless://",
        ):
            self.assertNotIn(forbidden, rendered)


class VPNObservabilityLoggingTests(SimpleTestCase):
    def test_health_and_reconcile_failure_records_have_no_node_identifier(self) -> None:
        from apps.vpn.services.health_check import _report_failure as report_health
        from apps.vpn.services.reconcile import _report_failure as report_reconcile

        with self.assertLogs(
            "apps.vpn.services.health_check", level=logging.WARNING
        ) as health:
            report_health(node_id=918273, error_code="agent_tls_failure")
        with self.assertLogs(
            "apps.vpn.services.reconcile", level=logging.WARNING
        ) as reconcile:
            report_reconcile(node_id=918273, error_code="snapshot_too_large")

        for record in (*health.records, *reconcile.records):
            self.assertFalse(hasattr(record, "node_id"))
            self.assertIn(
                record.error_code,
                {"agent_tls_failure", "snapshot_too_large"},
            )

    def test_metric_and_alert_logs_expose_only_bounded_safe_fields(self) -> None:
        from apps.vpn.observability import emit_vpn_alert, emit_vpn_metric

        with self.assertLogs("apps.vpn.observability", level=logging.INFO) as captured:
            emit_vpn_metric(VPNMetric(name="vpn_reconcile_failures_current", value=2))
            emit_vpn_alert(
                VPNAlert(
                    resource_kind="node", resource_id=7, error_code="revision_drift"
                )
            )

        output = " ".join(captured.output)
        self.assertIn("vpn_metric", output)
        self.assertIn("vpn_alert", output)
        self.assertNotIn("resource_id", output)
        for forbidden in ("UUID", "Authorization", "vless://", "snapshot_body"):
            self.assertNotIn(forbidden, output)

    @mock.patch("apps.vpn.infra.alert_dedupe.redis.Redis.from_url")
    def test_redis_outage_fails_open_for_business_paths(
        self, from_url: mock.Mock
    ) -> None:
        from apps.vpn.infra.alert_dedupe import get_vpn_alert_dedupe

        from_url.return_value.set.side_effect = ConnectionError("redis unavailable")

        self.assertFalse(
            get_vpn_alert_dedupe()(
                key="vpn-alert:fleet:0:no_ready_node", ttl_seconds=60
            )
        )


class VPNObservabilityTaskTests(SimpleTestCase):
    @mock.patch("apps.vpn.tasks.observability.get_collect_vpn_observability_service")
    def test_periodic_task_returns_bounded_counts(self, factory: mock.Mock) -> None:
        from apps.vpn.tasks.observability import collect_vpn_observability_task

        factory.return_value.return_value = VPNObservation(
            metrics=(VPNMetric(name="vpn_ready_nodes_current", value=2),),
            alerts=(
                VPNAlert(
                    resource_kind="node", resource_id=1, error_code="revision_drift"
                ),
            ),
        )

        self.assertEqual(
            collect_vpn_observability_task.run(),
            {"metrics": 1, "alerts": 1},
        )

    def test_celery_routes_and_schedules_periodic_collection(self) -> None:
        from config.settings.celery import CELERY_BEAT_SCHEDULE, CELERY_TASK_ROUTES

        self.assertEqual(
            CELERY_TASK_ROUTES["apps.vpn.collect_observability"],
            {"queue": "celery"},
        )
        self.assertEqual(
            CELERY_BEAT_SCHEDULE["collect-vpn-observability"]["task"],
            "apps.vpn.collect_observability",
        )

    @mock.patch("apps.vpn.tasks.reconcile.emit_vpn_metric")
    @mock.patch("apps.vpn.tasks.reconcile.get_reconcile_vpn_fleet_service")
    def test_reconcile_task_emits_failure_counter(
        self, factory: mock.Mock, emit_metric: mock.Mock
    ) -> None:
        from apps.vpn.services.reconcile import VPNFleetRunResult
        from apps.vpn.tasks.reconcile import reconcile_vpn_nodes_task

        factory.return_value.return_value = VPNFleetRunResult(succeeded=2, failed=3)

        self.assertEqual(
            reconcile_vpn_nodes_task.run(),
            {"succeeded": 2, "failed": 3},
        )
        metrics = [call.args[0] for call in emit_metric.call_args_list]
        self.assertEqual(
            [(metric.name, metric.value) for metric in metrics],
            [
                ("vpn_reconcile_delivery_success_total", 2),
                ("vpn_reconcile_delivery_failure_total", 3),
            ],
        )

    @mock.patch("apps.vpn.tasks.reconcile.emit_vpn_metric")
    @mock.patch("apps.vpn.tasks.reconcile.get_reconcile_vpn_fleet_service")
    def test_unexpected_reconcile_run_emits_failure_before_safe_reraise(
        self,
        factory: mock.Mock,
        emit_metric: mock.Mock,
    ) -> None:
        from apps.vpn.exceptions import VPNFleetUnexpectedError
        from apps.vpn.tasks.reconcile import reconcile_vpn_nodes_task

        factory.return_value.side_effect = VPNFleetUnexpectedError()

        with self.assertRaises(VPNFleetUnexpectedError):
            reconcile_vpn_nodes_task.run()

        metric = emit_metric.call_args.args[0]
        self.assertEqual(
            (metric.name, metric.value),
            ("vpn_reconcile_delivery_failure_total", 1),
        )

    @mock.patch("apps.vpn.tasks.notifications.get_safe_vpn_alert_service")
    @mock.patch("apps.vpn.tasks.notifications.emit_vpn_metric")
    @mock.patch("apps.vpn.tasks.notifications.get_send_vpn_ready_notification_service")
    def test_notification_failure_emits_safe_counter_and_alert_then_retries(
        self,
        factory: mock.Mock,
        emit_metric: mock.Mock,
        alert_factory: mock.Mock,
    ) -> None:
        from apps.vpn.tasks.notifications import send_vpn_ready_notification_task

        factory.return_value.side_effect = RuntimeError(
            "vless://uuid@example.test?token=secret"
        )

        with self.assertRaisesRegex(
            RuntimeError, "vpn_notification_failure"
        ) as failure:
            send_vpn_ready_notification_task.run(access_id=71, revision=4)

        self.assertNotIn("vless://", str(failure.exception))

        metric = emit_metric.call_args.args[0]
        self.assertEqual(
            (metric.name, metric.value),
            ("vpn_notification_delivery_failure_total", 1),
        )
        alert = alert_factory.return_value.call_args.kwargs["alert"]
        self.assertEqual(
            (alert.resource_kind, alert.resource_id, alert.error_code),
            ("notification", 71, "notification_failure"),
        )
        self.assertNotIn("vless://", repr(alert))

    @mock.patch("apps.vpn.tasks.notifications.get_safe_vpn_alert_service")
    @mock.patch("apps.vpn.tasks.notifications.emit_vpn_metric")
    @mock.patch("apps.vpn.tasks.notifications.get_send_vpn_ready_notification_service")
    def test_telemetry_outage_does_not_mask_notification_result(
        self,
        factory: mock.Mock,
        emit_metric: mock.Mock,
        alert_factory: mock.Mock,
    ) -> None:
        from apps.vpn.tasks.notifications import send_vpn_ready_notification_task

        factory.return_value.return_value = True
        emit_metric.side_effect = OSError("sink down")
        alert_factory.return_value.side_effect = OSError("redis down")

        self.assertTrue(send_vpn_ready_notification_task.run(access_id=1, revision=1))

    @mock.patch("apps.vpn.tasks.notifications.emit_vpn_metric")
    @mock.patch("apps.vpn.tasks.notifications.get_send_vpn_ready_notification_service")
    def test_notification_success_emits_delivery_success_counter(
        self,
        factory: mock.Mock,
        emit_metric: mock.Mock,
    ) -> None:
        from apps.vpn.tasks.notifications import send_vpn_ready_notification_task

        factory.return_value.return_value = True

        self.assertTrue(send_vpn_ready_notification_task.run(access_id=1, revision=1))
        metric = emit_metric.call_args.args[0]
        self.assertEqual(
            (metric.name, metric.value),
            ("vpn_notification_delivery_success_total", 1),
        )


class VPNObservabilityOperatorConfigTests(SimpleTestCase):
    root = Path(__file__).resolve().parents[4]

    def test_thresholds_and_operator_responses_are_documented(self) -> None:
        vpn_docs = (self.root / "docs/apps/VPN.md").read_text()
        deploy_docs = (self.root / "docs/DEPLOY.md").read_text()
        env_example = (self.root / ".env.example").read_text()

        for variable in (
            "VPN_OBSERVABILITY_STALE_RECEIPT_SECONDS",
            "VPN_OBSERVABILITY_DRIFT_SECONDS",
            "VPN_OBSERVABILITY_AUTH_TLS_SECONDS",
            "VPN_OBSERVABILITY_ALERT_DEDUPE_SECONDS",
        ):
            self.assertIn(variable, env_example)
            self.assertIn(variable, vpn_docs)
        for alert_code in (
            "stale_receipt",
            "no_ready_node",
            "incompatible_contract",
            "snapshot_too_large",
            "revision_drift",
            "agent_unauthorized",
            "agent_tls_failure",
            "notification_failure",
        ):
            self.assertIn(alert_code, deploy_docs)

    def test_flower_is_bounded_persistent_and_nginx_route_log_has_no_uri(self) -> None:
        compose = (self.root / "docker-compose.yml").read_text()
        nginx = (self.root / "nginx/nginx.conf").read_text()
        subscription_log_format = next(
            line
            for line in nginx.splitlines()
            if line.startswith("log_format vpn_subscription")
        )

        self.assertIn("--persistent=True", compose)
        self.assertIn("--db=/app/data/flower.db", compose)
        self.assertIn("--max_tasks=10000", compose)
        for unsafe_variable in ("$request ", "$request_uri", "$uri", "$args"):
            self.assertNotIn(unsafe_variable, subscription_log_format)
