from __future__ import annotations

import json
from unittest import mock

import responses
from django.test import TestCase

from apps.vds.services import get_update_key_infra_service
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


@mock.patch("apps.notifications.services.send_notification_service.send_telegram_message")
@mock.patch("apps.core.decorators._log_infra_error")
class TestUpdateKeyInfraService(TestCase):
    def setUp(self) -> None:
        self.key = MTPRotoKeyFactory()
        self.server = self.key.vds

    @responses.activate
    @mock.patch("apps.vds.services.update_key_infra_service.update_key_on_another_vds_instances_task")
    def test_sends_patch_to_target_server(self, mock_task, mock_log, mock_send) -> None:
        responses.add(
            method=responses.PATCH,
            url=f"{self.server.internal_url}/api/users",
            json={"key": "new_token", "tls_domain": "new.domain"},
        )

        result = get_update_key_infra_service()(
            server=self.server,
            username=str(self.key.user.username),
        )

        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(responses.calls[0].request.method, "PATCH")
        body = json.loads(responses.calls[0].request.body)
        self.assertEqual(body["username"], str(self.key.user.username))
        self.assertEqual(result.key, "new_token")
        self.assertEqual(result.tls_domain, "new.domain")

    @responses.activate
    @mock.patch("apps.vds.services.update_key_infra_service.update_key_on_another_vds_instances_task")
    def test_dispatches_patch_replication_task(self, mock_task, mock_log, mock_send) -> None:
        responses.add(
            method=responses.PATCH,
            url=f"{self.server.internal_url}/api/users",
            json={"key": "new_token", "tls_domain": "new.domain"},
        )

        get_update_key_infra_service()(
            server=self.server,
            username=str(self.key.user.username),
        )

        mock_task.delay.assert_called_once_with(
            exclude=self.server.pk,
            username=str(self.key.user.username),
            secret=mock.ANY,
        )

    @responses.activate
    @mock.patch("apps.vds.services.update_key_infra_service.update_key_on_another_vds_instances_task")
    def test_can_target_server_different_from_key_vds(self, mock_task, mock_log, mock_send) -> None:
        new_server = VDSInstanceFactory()
        responses.add(
            method=responses.PATCH,
            url=f"{new_server.internal_url}/api/users",
            json={"key": "new_token", "tls_domain": "new.domain"},
        )

        get_update_key_infra_service()(
            server=new_server,
            username=str(self.key.user.username),
        )

        self.assertEqual(
            responses.calls[0].request.url,
            f"{new_server.internal_url}/api/users",
        )
