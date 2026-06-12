from __future__ import annotations

from unittest.mock import patch

import responses
from django.test import TestCase

from apps.vds.tasks import _handle_replication_failure
from apps.vds.tests.factories import VDSInstanceFactory


class TestHandleReplicationFailure(TestCase):
    def setUp(self) -> None:
        self.server = VDSInstanceFactory(is_healthy=True)

    @patch("apps.core.telegram.transport.send_telegram_message")
    def test_marks_server_as_unhealthy(self, mock_send) -> None:
        _handle_replication_failure(
            server_id=self.server.pk,
            username="john",
            exc=Exception("Connection refused"),
        )

        self.server.refresh_from_db()
        self.assertFalse(self.server.is_healthy)

    @patch("apps.core.telegram.transport.send_telegram_message")
    def test_sends_admin_notification(self, mock_send) -> None:
        _handle_replication_failure(
            server_id=self.server.pk,
            username="john",
            exc=Exception("Connection refused"),
        )

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        self.assertIn("john", str(call_kwargs))

    @patch("apps.core.telegram.transport.send_telegram_message")
    def test_does_not_crash_when_server_not_found(self, mock_send) -> None:
        # Should not raise even if server_id is invalid
        _handle_replication_failure(
            server_id=99999,
            username="john",
            exc=Exception("boom"),
        )
        mock_send.assert_called_once()


class TestReplicateKeyAddToServerTask(TestCase):
    def setUp(self) -> None:
        self.server = VDSInstanceFactory()

    @responses.activate
    def test_calls_service_on_success(self) -> None:
        from apps.vds.tasks import replicate_key_add_to_server_task

        responses.add(
            method=responses.POST,
            url=f"{self.server.internal_url}/api/users",
            json={"status": "ok"},
        )

        replicate_key_add_to_server_task.apply(
            args=[self.server.pk, "john", "abc123"]
        )

        self.assertEqual(len(responses.calls), 1)

    @patch("apps.vds.tasks._handle_replication_failure")
    def test_calls_handle_when_retries_exhausted(self, mock_handle) -> None:
        from celery.exceptions import MaxRetriesExceededError

        from apps.vds.tasks import replicate_key_add_to_server_task

        original_exc = Exception("Connection refused")

        with patch(
            "apps.vds.services.replicate_key_add_to_server_infra_service."
            "get_replicate_key_add_to_server_infra_service"
        ) as mock_factory:
            mock_factory.return_value.side_effect = original_exc
            # Patch task.retry to raise MaxRetriesExceededError to simulate exhausted retries
            with patch.object(replicate_key_add_to_server_task, "retry", side_effect=MaxRetriesExceededError):
                replicate_key_add_to_server_task.apply(
                    args=[self.server.pk, "john", "abc123"],
                )

        mock_handle.assert_called_once_with(
            server_id=self.server.pk,
            username="john",
            exc=original_exc,
        )


class TestReplicateKeyUpdateToServerTask(TestCase):
    def setUp(self) -> None:
        self.server = VDSInstanceFactory()

    @responses.activate
    def test_calls_service_on_success(self) -> None:
        from apps.vds.tasks import replicate_key_update_to_server_task

        responses.add(
            method=responses.PATCH,
            url=f"{self.server.internal_url}/api/users",
            json={"status": "ok"},
        )

        replicate_key_update_to_server_task.apply(
            args=[self.server.pk, "john", "abc123"]
        )

        self.assertEqual(len(responses.calls), 1)

    @patch("apps.vds.tasks._handle_replication_failure")
    def test_calls_handle_when_retries_exhausted(self, mock_handle) -> None:
        from celery.exceptions import MaxRetriesExceededError

        from apps.vds.tasks import replicate_key_update_to_server_task

        with patch(
            "apps.vds.services.replicate_key_update_to_server_infra_service."
            "get_replicate_key_update_to_server_infra_service"
        ) as mock_factory:
            mock_factory.return_value.side_effect = Exception("Connection refused")
            # Patch task.retry to raise MaxRetriesExceededError to simulate exhausted retries
            with patch.object(replicate_key_update_to_server_task, "retry", side_effect=MaxRetriesExceededError):
                replicate_key_update_to_server_task.apply(
                    args=[self.server.pk, "john", "abc123"],
                )

        mock_handle.assert_called_once()
