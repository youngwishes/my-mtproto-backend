from __future__ import annotations

from unittest.mock import patch

import responses
from django.test import TestCase

from apps.vds.tasks import migrate_vds_keys_task
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestMigrateVdsKeysTask(TestCase):
    @responses.activate
    def test_delegates_to_service(self) -> None:
        source = VDSInstanceFactory()
        target = VDSInstanceFactory()
        MTPRotoKeyFactory(vds=source, token="abc123")
        responses.add(
            method=responses.POST,
            url=f"{target.internal_url}/api/users",
            json={"status": "ok"},
        )

        migrate_vds_keys_task(from_instance_id=source.pk)

        self.assertEqual(len(responses.calls), 1)
