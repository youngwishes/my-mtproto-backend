from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

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
