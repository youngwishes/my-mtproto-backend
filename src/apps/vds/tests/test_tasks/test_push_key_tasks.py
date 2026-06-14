from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import responses
from django.test import TestCase
from django.utils import timezone

from apps.users.tests.factories import SystemUserFactory
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestPushKeyToServersTask(TestCase):
    def setUp(self) -> None:
        self.user = SystemUserFactory(username="john")
        # Ключ не привязан к серверу — валиден на всём флоте.
        self.key = MTPRotoKeyFactory(
            user=self.user,
            token="secret-token",
            is_active=True,
            was_deleted=False,
            expired_date=timezone.now() + timedelta(days=30),
        )

    @patch("apps.vds.tasks.push_key_to_server_task.delay")
    def test_fans_out_only_to_healthy_servers(self, mock_delay) -> None:
        from apps.vds.tasks import push_key_to_servers_task

        healthy_1 = VDSInstanceFactory(is_healthy=True)
        healthy_2 = VDSInstanceFactory(is_healthy=True)
        VDSInstanceFactory(is_healthy=False)
        VDSInstanceFactory(is_active=False, is_healthy=True)

        push_key_to_servers_task(key_id=self.key.pk)

        called_server_ids = {call.args[0] for call in mock_delay.call_args_list}
        self.assertEqual(called_server_ids, {healthy_1.pk, healthy_2.pk})
        for call in mock_delay.call_args_list:
            self.assertEqual(call.args[1], "john")
            self.assertEqual(call.args[2], "secret-token")

    @patch("apps.vds.tasks.push_key_to_server_task.delay")
    def test_does_nothing_for_missing_key(self, mock_delay) -> None:
        from apps.vds.tasks import push_key_to_servers_task

        VDSInstanceFactory(is_healthy=True)
        push_key_to_servers_task(key_id=999999)

        mock_delay.assert_not_called()


class TestPushKeyToServerTask(TestCase):
    def setUp(self) -> None:
        self.server = VDSInstanceFactory()

    @responses.activate
    def test_calls_service_on_success(self) -> None:
        from apps.vds.tasks import push_key_to_server_task

        responses.add(
            method=responses.POST,
            url=f"{self.server.internal_url}/api/users",
            json={"status": "ok"},
        )

        push_key_to_server_task.apply(args=[self.server.pk, "john", "abc123"])

        self.assertEqual(len(responses.calls), 1)

    @patch("apps.vds.tasks._handle_replication_failure")
    def test_marks_unhealthy_when_retries_exhausted(self, mock_handle) -> None:
        from celery.exceptions import MaxRetriesExceededError

        from apps.vds.tasks import push_key_to_server_task

        original_exc = Exception("Connection refused")

        with patch(
            "apps.vds.services.push_key_to_server_infra_service."
            "get_push_key_to_server_infra_service"
        ) as mock_factory:
            mock_factory.return_value.side_effect = original_exc
            with patch.object(
                push_key_to_server_task, "retry", side_effect=MaxRetriesExceededError
            ):
                push_key_to_server_task.apply(args=[self.server.pk, "john", "abc123"])

        mock_handle.assert_called_once_with(
            server_id=self.server.pk,
            username="john",
            exc=original_exc,
        )
