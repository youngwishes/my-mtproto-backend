from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.vds.exceptions import VDSNotAvailable
from apps.vds.tasks import check_vds_health_task
from apps.vds.tests.factories import VDSInstanceFactory


class TestCheckVdsHealthTask(TestCase):
    def setUp(self) -> None:
        self.healthy_server = VDSInstanceFactory(is_healthy=True)
        self.unhealthy_server = VDSInstanceFactory(is_healthy=False)

    @patch("apps.vds.tasks.sync_keys_to_vds_task")
    @patch(
        "apps.vds.services.vds_health_check_infra_service."
        "get_vds_health_check_infra_service"
    )
    def test_recovers_server_and_triggers_sync(self, mock_service_factory, mock_sync) -> None:
        mock_service_factory.return_value.return_value = True

        check_vds_health_task()

        self.unhealthy_server.refresh_from_db()
        self.assertTrue(self.unhealthy_server.is_healthy)
        mock_sync.delay.assert_called_once_with(instance_id=self.unhealthy_server.pk)

    @patch("apps.vds.tasks.sync_keys_to_vds_task")
    @patch(
        "apps.vds.services.vds_health_check_infra_service."
        "get_vds_health_check_infra_service"
    )
    def test_skips_still_unreachable_server(self, mock_service_factory, mock_sync) -> None:
        mock_service_factory.return_value.return_value = False

        check_vds_health_task()

        self.unhealthy_server.refresh_from_db()
        self.assertFalse(self.unhealthy_server.is_healthy)
        mock_sync.delay.assert_not_called()

    @patch("apps.vds.tasks.sync_keys_to_vds_task")
    @patch(
        "apps.vds.services.vds_health_check_infra_service."
        "get_vds_health_check_infra_service"
    )
    def test_does_not_check_already_healthy_servers(self, mock_service_factory, mock_sync) -> None:
        mock_service_factory.return_value.return_value = True

        check_vds_health_task()

        # sync.delay called exactly once — only for unhealthy_server, not healthy_server
        mock_sync.delay.assert_called_once_with(instance_id=self.unhealthy_server.pk)

    @patch("apps.vds.tasks.sync_keys_to_vds_task")
    @patch(
        "apps.vds.services.vds_health_check_infra_service."
        "get_vds_health_check_infra_service"
    )
    def test_handles_multiple_unhealthy_servers(self, mock_service_factory, mock_sync) -> None:
        second_unhealthy = VDSInstanceFactory(is_healthy=False)
        mock_service_factory.return_value.return_value = True

        check_vds_health_task()

        self.assertEqual(mock_sync.delay.call_count, 2)
        called_ids = {c.kwargs["instance_id"] for c in mock_sync.delay.call_args_list}
        self.assertIn(self.unhealthy_server.pk, called_ids)
        self.assertIn(second_unhealthy.pk, called_ids)

    @patch("apps.vds.tasks.sync_keys_to_vds_task")
    @patch("apps.vds.services.get_remove_dead_keys_from_vds_infra_service")
    @patch(
        "apps.vds.services.vds_health_check_infra_service."
        "get_vds_health_check_infra_service"
    )
    def test_cleanup_precedes_recovery_and_unavailable_vds_isolated(
        self,
        mock_health_check_factory,
        mock_cleanup_factory,
        mock_sync,
    ) -> None:
        recovered_server = VDSInstanceFactory(is_healthy=False)
        cleanup_failed_server = VDSInstanceFactory(is_healthy=False)
        second_recovered_server = VDSInstanceFactory(is_healthy=False)
        servers = {
            self.unhealthy_server.pk: self.unhealthy_server,
            recovered_server.pk: recovered_server,
            cleanup_failed_server.pk: cleanup_failed_server,
            second_recovered_server.pk: second_recovered_server,
        }
        recovery_events = []

        mock_health_check_factory.return_value.side_effect = (
            lambda *, instance_id: instance_id != self.unhealthy_server.pk
        )

        def remove_dead_keys(*, instance_id: int) -> None:
            if instance_id == cleanup_failed_server.pk:
                raise VDSNotAvailable(telegram_id=[])

            server = servers[instance_id]
            server.refresh_from_db()
            self.assertFalse(server.is_healthy)
            recovery_events.append(("cleanup", instance_id))

        def queue_sync(*, instance_id: int) -> None:
            server = servers[instance_id]
            server.refresh_from_db()
            self.assertTrue(server.is_healthy)
            recovery_events.append(("sync", instance_id))

        mock_cleanup_factory.return_value.side_effect = remove_dead_keys
        mock_sync.delay.side_effect = queue_sync

        check_vds_health_task()

        self.unhealthy_server.refresh_from_db()
        recovered_server.refresh_from_db()
        cleanup_failed_server.refresh_from_db()
        second_recovered_server.refresh_from_db()
        self.assertFalse(self.unhealthy_server.is_healthy)
        self.assertTrue(recovered_server.is_healthy)
        self.assertFalse(cleanup_failed_server.is_healthy)
        self.assertTrue(second_recovered_server.is_healthy)
        self.assertEqual(
            [call.kwargs["instance_id"] for call in mock_cleanup_factory.return_value.call_args_list],
            [recovered_server.pk, cleanup_failed_server.pk, second_recovered_server.pk],
        )
        self.assertEqual(
            [call.kwargs["instance_id"] for call in mock_sync.delay.call_args_list],
            [recovered_server.pk, second_recovered_server.pk],
        )
        self.assertEqual(
            recovery_events,
            [
                ("cleanup", recovered_server.pk),
                ("sync", recovered_server.pk),
                ("cleanup", second_recovered_server.pk),
                ("sync", second_recovered_server.pk),
            ],
        )
