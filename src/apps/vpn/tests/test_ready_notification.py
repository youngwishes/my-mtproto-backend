from __future__ import annotations

from unittest import mock

from django.test import TestCase, override_settings

from apps.vpn.enums import VPNAccessState
from apps.vpn.services.send_ready_notification import (
    get_send_vpn_ready_notification_service,
)
from apps.vpn.tasks.notifications import recover_vpn_ready_notifications_task
from apps.vpn.tests.factories import VPNAccessFactory


@override_settings(
    VPN_SUBSCRIPTION_BASE_URL="https://vpn.example.com/api/v1/vpn/subscriptions"
)
class SendVPNReadyNotificationServiceTests(TestCase):
    def setUp(self) -> None:
        self.access = VPNAccessFactory(
            state=VPNAccessState.PREPARING,
        )
        self.access.user.username = "123456789"
        self.access.user.save(update_fields=("username",))
        self.access.published_uuid = self.access.desired_uuid
        self.access.published_revision = self.access.desired_revision
        self.access.state = VPNAccessState.READY
        self.access.save(
            update_fields=(
                "published_uuid",
                "published_revision",
                "state",
                "updated_at",
            )
        )

    @mock.patch("apps.core.bot.TelegramBot")
    def test_marker_advances_only_after_successful_send(
        self, telegram_bot: mock.Mock
    ) -> None:
        service = get_send_vpn_ready_notification_service()

        sent = service(access_id=self.access.pk, revision=self.access.desired_revision)

        self.assertTrue(sent)
        self.access.refresh_from_db()
        self.assertEqual(
            self.access.ready_notification_revision, self.access.desired_revision
        )
        message = telegram_bot.return_value.send_message.call_args.kwargs["text"]
        self.assertIn(self.access.subscription_token, message)

    @mock.patch("apps.core.bot.TelegramBot")
    def test_telegram_failure_keeps_durable_marker_pending(
        self, telegram_bot: mock.Mock
    ) -> None:
        telegram_bot.return_value.send_message.side_effect = RuntimeError(
            "telegram down"
        )

        with self.assertRaises(RuntimeError):
            get_send_vpn_ready_notification_service()(
                access_id=self.access.pk,
                revision=self.access.desired_revision,
            )

        self.access.refresh_from_db()
        self.assertEqual(self.access.ready_notification_revision, 0)

    @mock.patch("apps.vpn.tasks.notifications._enqueue_notification")
    def test_lost_enqueue_is_recovered_from_durable_selector(
        self, enqueue: mock.Mock
    ) -> None:
        recovered = recover_vpn_ready_notifications_task.run()

        self.assertEqual(recovered, 1)
        enqueue.assert_called_once_with(
            access_id=self.access.pk,
            revision=self.access.desired_revision,
        )

    @mock.patch("apps.vpn.tasks.notifications._enqueue_notification")
    @mock.patch("apps.vpn.tasks.notifications.get_safe_vpn_alert_service")
    @mock.patch("apps.vpn.tasks.notifications.emit_vpn_metric")
    def test_broker_failure_leaves_work_selectable_and_emits_safe_failure(
        self,
        emit_metric: mock.Mock,
        alert_factory: mock.Mock,
        enqueue: mock.Mock,
    ) -> None:
        enqueue.side_effect = RuntimeError("broker down")

        recovered = recover_vpn_ready_notifications_task.run()

        self.assertEqual(recovered, 0)
        self.access.refresh_from_db()
        self.assertEqual(self.access.ready_notification_revision, 0)
        metric = emit_metric.call_args.args[0]
        self.assertEqual(
            (metric.name, metric.value),
            ("vpn_notification_delivery_failure_total", 1),
        )
        alert = alert_factory.return_value.call_args.kwargs["alert"]
        self.assertEqual(alert.error_code, "notification_failure")
