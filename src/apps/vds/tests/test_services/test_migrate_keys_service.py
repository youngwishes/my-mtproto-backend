from __future__ import annotations

import json
from unittest.mock import patch

import responses
from django.test import TestCase

from apps.vds.services import get_migrate_vds_keys_service
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestMigrateVdsKeysService(TestCase):
    def setUp(self) -> None:
        self.source = VDSInstanceFactory()
        self.target_1 = VDSInstanceFactory()
        self.target_2 = VDSInstanceFactory()

    def _mock_target_endpoints(self) -> None:
        for server in (self.target_1, self.target_2):
            responses.add(
                method=responses.POST,
                url=f"{server.internal_url}/api/users",
                json={"status": "ok"},
            )

    @responses.activate
    def test_migrates_keys_to_all_other_instances(self) -> None:
        key = MTPRotoKeyFactory(vds=self.source, token="abc123")
        self._mock_target_endpoints()

        get_migrate_vds_keys_service()(from_instance_id=self.source.pk)

        self.assertEqual(len(responses.calls), 2)
        for call in responses.calls:
            body = json.loads(call.request.body)
            self.assertEqual(body["username"], key.user.username)
            self.assertEqual(body["secret"], str(key.token))

    @responses.activate
    def test_does_not_post_to_source_instance(self) -> None:
        MTPRotoKeyFactory(vds=self.source, token="abc123")
        responses.add(
            method=responses.POST,
            url=f"{self.source.internal_url}/api/users",
            json={"status": "ok"},
        )
        self._mock_target_endpoints()

        get_migrate_vds_keys_service()(from_instance_id=self.source.pk)

        called_urls = [call.request.url for call in responses.calls]
        self.assertNotIn(f"{self.source.internal_url}/api/users", called_urls)

    @responses.activate
    def test_skips_key_without_token(self) -> None:
        MTPRotoKeyFactory(vds=self.source, token="")
        self._mock_target_endpoints()

        get_migrate_vds_keys_service()(from_instance_id=self.source.pk)

        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_skips_key_without_username(self) -> None:
        MTPRotoKeyFactory(vds=self.source, token="abc123", user__username="")
        self._mock_target_endpoints()

        get_migrate_vds_keys_service()(from_instance_id=self.source.pk)

        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_multiple_keys_migrated(self) -> None:
        MTPRotoKeyFactory(vds=self.source, token="key1")
        MTPRotoKeyFactory(vds=self.source, token="key2")
        self._mock_target_endpoints()
        self._mock_target_endpoints()

        get_migrate_vds_keys_service()(from_instance_id=self.source.pk)

        self.assertEqual(len(responses.calls), 4)

    @responses.activate
    def test_continues_on_http_error_and_notifies_admin(self) -> None:
        MTPRotoKeyFactory(vds=self.source, token="key1")
        responses.add(
            method=responses.POST,
            url=f"{self.target_1.internal_url}/api/users",
            json={"error": "fail"},
            status=500,
        )
        responses.add(
            method=responses.POST,
            url=f"{self.target_2.internal_url}/api/users",
            json={"status": "ok"},
        )

        with patch("apps.vds.services.migrate_keys_infra_service.send_telegram_message"):
            get_migrate_vds_keys_service()(from_instance_id=self.source.pk)

        self.assertEqual(len(responses.calls), 2)
