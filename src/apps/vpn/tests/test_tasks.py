from __future__ import annotations

from unittest.mock import patch

import requests
from celery.exceptions import Retry
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.vpn.tasks import deliver_vpn_profile_task
from apps.vpn.tests.factories import VPNInstanceFactory, VPNSubscriptionFactory


class TestDeliverVPNProfileTask(TestCase):
    def setUp(self) -> None:
        self.subscription = VPNSubscriptionFactory(expired_at=timezone.now())
        self.instance = VPNInstanceFactory()

    @patch("apps.vpn.tasks.get_node_client_service")
    def test_put_delivery_calls_agent_client_for_profile(self, get_node_client_service) -> None:
        deliver_vpn_profile_task.run(
            subscription_id=self.subscription.pk,
            instance_id=self.instance.pk,
            operation="put",
        )

        get_node_client_service.return_value.put_profile.assert_called_once()

    @patch("apps.vpn.tasks.get_node_client_service")
    def test_delete_delivery_calls_agent_client_for_profile(self, get_node_client_service) -> None:
        deliver_vpn_profile_task.run(
            subscription_id=self.subscription.pk,
            instance_id=self.instance.pk,
            operation="delete",
        )

        get_node_client_service.return_value.delete_profile.assert_called_once_with(
            instance=self.instance,
            access_id=self.subscription.pk,
        )

    @patch("apps.vpn.tasks.get_node_client_service")
    def test_timeout_retries_with_fixed_ten_second_countdown(self, get_node_client_service) -> None:
        get_node_client_service.return_value.put_profile.side_effect = requests.Timeout()

        with patch.object(deliver_vpn_profile_task, "retry", side_effect=Retry()) as retry:
            with self.assertRaises(Retry):
                deliver_vpn_profile_task.run(
                    subscription_id=self.subscription.pk,
                    instance_id=self.instance.pk,
                    operation="put",
                )

        self.assertEqual(retry.call_args.kwargs["countdown"], 10)

    @patch("apps.vpn.tasks.get_node_client_service")
    def test_server_error_retries_with_fixed_ten_second_countdown(self, get_node_client_service) -> None:
        response = requests.Response()
        response.status_code = 503
        get_node_client_service.return_value.put_profile.side_effect = requests.HTTPError(
            response=response,
        )

        with patch.object(deliver_vpn_profile_task, "retry", side_effect=Retry()) as retry:
            with self.assertRaises(Retry):
                deliver_vpn_profile_task.run(
                    subscription_id=self.subscription.pk,
                    instance_id=self.instance.pk,
                    operation="put",
                )

        self.assertEqual(retry.call_args.kwargs["countdown"], 10)

    @patch("apps.vpn.tasks._notify_delivery_failure")
    @patch("apps.vpn.tasks.get_node_client_service")
    def test_client_error_is_terminal_and_does_not_retry(
        self,
        get_node_client_service,
        notify_delivery_failure,
    ) -> None:
        response = requests.Response()
        response.status_code = 400
        get_node_client_service.return_value.put_profile.side_effect = requests.HTTPError(
            response=response,
        )

        deliver_vpn_profile_task.run(
            subscription_id=self.subscription.pk,
            instance_id=self.instance.pk,
            operation="put",
        )

        notify_delivery_failure.assert_called_once()

    @patch("apps.vpn.tasks._notify_delivery_failure")
    @patch("apps.vpn.tasks.get_node_client_service")
    def test_exhausted_timeout_retries_send_terminal_alert(
        self,
        get_node_client_service,
        notify_delivery_failure,
    ) -> None:
        get_node_client_service.return_value.put_profile.side_effect = requests.Timeout()
        deliver_vpn_profile_task.push_request(retries=3)
        try:
            with patch.object(deliver_vpn_profile_task, "retry") as retry:
                deliver_vpn_profile_task.run(
                    subscription_id=self.subscription.pk,
                    instance_id=self.instance.pk,
                    operation="put",
                )
        finally:
            deliver_vpn_profile_task.pop_request()

        retry.assert_not_called()
        notify_delivery_failure.assert_called_once()

    @patch("apps.vpn.tasks.send_telegram_message")
    def test_terminal_alert_names_user_node_and_operation_without_credentials(
        self,
        send_telegram_message,
    ) -> None:
        self.subscription.user.username = "12345678"
        self.subscription.user.save(update_fields=["username"])

        from apps.vpn.tasks import _notify_delivery_failure

        _notify_delivery_failure(
            subscription=self.subscription,
            instance=self.instance,
            operation="put",
        )

        text = send_telegram_message.call_args.kwargs["text"]
        self.assertIn("12345678", text)
        self.assertIn(self.instance.name, text)
        self.assertIn("PUT", text)
        self.assertNotIn(str(self.subscription.vless_uuid), text)
        self.assertNotIn(self.subscription.hysteria_secret, text)

    @override_settings(VPN_AGENT_TOKEN=None)
    @patch("apps.vpn.tasks.send_telegram_message")
    @patch("apps.vpn.services.node_client_service.requests.put")
    def test_missing_agent_token_is_terminal_without_retry_or_http(
        self,
        put,
        send_telegram_message,
    ) -> None:
        with patch.object(deliver_vpn_profile_task, "retry") as retry:
            deliver_vpn_profile_task.run(
                subscription_id=self.subscription.pk,
                instance_id=self.instance.pk,
                operation="put",
            )

        send_telegram_message.assert_called_once()
        retry.assert_not_called()
        put.assert_not_called()

    @override_settings(VPN_AGENT_TOKEN="")
    @patch("apps.vpn.tasks.send_telegram_message")
    @patch("apps.vpn.services.node_client_service.requests.put")
    def test_blank_agent_token_is_terminal_without_retry_or_http(
        self,
        put,
        send_telegram_message,
    ) -> None:
        with patch.object(deliver_vpn_profile_task, "retry") as retry:
            deliver_vpn_profile_task.run(
                subscription_id=self.subscription.pk,
                instance_id=self.instance.pk,
                operation="put",
            )

        send_telegram_message.assert_called_once()
        retry.assert_not_called()
        put.assert_not_called()
