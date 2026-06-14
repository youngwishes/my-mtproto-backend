from __future__ import annotations

from datetime import timedelta

import responses
from django.test import TestCase
from django.utils import timezone

from apps.vds.tasks import migrate_vds_keys_task
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestMigrateVdsKeysTask(TestCase):
    @responses.activate
    def test_delegates_to_service(self) -> None:
        source = VDSInstanceFactory()
        target = VDSInstanceFactory()
        MTPRotoKeyFactory(
            vds=None, token="abc123", expired_date=timezone.now() + timedelta(days=10)
        )
        responses.add(
            method=responses.POST,
            url=f"{target.internal_url}/api/users",
            json={"status": "ok"},
        )

        migrate_vds_keys_task(from_instance_id=source.pk)

        self.assertEqual(len(responses.calls), 1)
