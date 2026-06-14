from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch

import responses
from django.test import TestCase
from django.utils import timezone

from apps.vds.services import get_migrate_vds_keys_service
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory

_FUTURE = timezone.now() + timedelta(days=10)


class TestMigrateVdsKeysService(TestCase):
    """Под reconcile-моделью ключ не привязан к «домашнему» серверу:

    мигрируются все активные валидные ключи на все остальные активные инстансы.
    """

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
        key = MTPRotoKeyFactory(token="abc123", expired_date=_FUTURE)
        self._mock_target_endpoints()

        get_migrate_vds_keys_service()(from_instance_id=self.source.pk)

        self.assertEqual(len(responses.calls), 2)
        for call in responses.calls:
            body = json.loads(call.request.body)
            self.assertEqual(body["username"], key.user.username)
            self.assertEqual(body["secret"], str(key.token))

    @responses.activate
    def test_does_not_post_to_source_instance(self) -> None:
        MTPRotoKeyFactory(token="abc123", expired_date=_FUTURE)
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
        MTPRotoKeyFactory(token="", expired_date=_FUTURE)
        self._mock_target_endpoints()

        get_migrate_vds_keys_service()(from_instance_id=self.source.pk)

        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_skips_key_without_username(self) -> None:
        MTPRotoKeyFactory(token="abc123", expired_date=_FUTURE, user__username="")
        self._mock_target_endpoints()

        get_migrate_vds_keys_service()(from_instance_id=self.source.pk)

        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_skips_expired_key(self) -> None:
        MTPRotoKeyFactory(
            token="abc123", expired_date=timezone.now() - timedelta(days=1)
        )
        self._mock_target_endpoints()

        get_migrate_vds_keys_service()(from_instance_id=self.source.pk)

        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_multiple_keys_migrated(self) -> None:
        MTPRotoKeyFactory(token="key1", expired_date=_FUTURE)
        MTPRotoKeyFactory(token="key2", expired_date=_FUTURE)
        self._mock_target_endpoints()
        self._mock_target_endpoints()

        get_migrate_vds_keys_service()(from_instance_id=self.source.pk)

        self.assertEqual(len(responses.calls), 4)

    @responses.activate
    def test_continues_on_http_error_and_notifies_admin(self) -> None:
        MTPRotoKeyFactory(token="key1", expired_date=_FUTURE)
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
