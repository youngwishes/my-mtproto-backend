from __future__ import annotations

from unittest.mock import call, patch

from django.test import TestCase

from apps.vds.models import VDSInstance
from apps.vds.tasks import add_key_to_another_vds_instances_task
from apps.vds.tests.factories import VDSInstanceFactory


class TestAddUserTask(TestCase):
    def setUp(self) -> None:
        self.vds = VDSInstanceFactory()
        for _ in range(5):
            VDSInstanceFactory()

    @patch("apps.vds.tasks.replicate_key_add_to_server_task")
    def test_add_key_service(self, mock_task) -> None:
        add_key_to_another_vds_instances_task(exclude=self.vds.pk, username="John", secret="test")

        other_servers = VDSInstance.objects.active().exclude(pk=self.vds.pk)
        self.assertEqual(mock_task.delay.call_count, other_servers.count())

        expected_calls = [call(server.pk, "John", "test") for server in other_servers]
        mock_task.delay.assert_has_calls(expected_calls, any_order=True)
