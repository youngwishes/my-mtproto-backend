from __future__ import annotations

from datetime import timedelta
from unittest import mock

import responses
from django.test import TestCase
from django.utils import timezone

from apps.vds.services.remove_expired_keys_from_vds_infra_service import (
    get_remove_expired_keys_from_vds_infra_service,
)
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestRemoveExpiredKeysFromVdsInfraService(TestCase):
    def setUp(self) -> None:
        self.server_a = VDSInstanceFactory()
        self.server_b = VDSInstanceFactory()

    def _add_delete_response(self, server) -> None:
        responses.add(
            method=responses.DELETE,
            url=server.internal_url + "/api/users",
        )

    @mock.patch("apps.vds.services.remove_key_infra_service.RemoveUserKeyInfraService.__call__")
    def test_no_expired_keys_exits_early(self, infra_service) -> None:
        MTPRotoKeyFactory(
            vds=self.server_a,
            expired_date=timezone.now() + timedelta(days=1),
        )
        get_remove_expired_keys_from_vds_infra_service()()
        self.assertEqual(infra_service.call_count, 0)

    @responses.activate
    def test_removes_expired_keys_from_all_vds_servers(self) -> None:
        self._add_delete_response(self.server_a)
        self._add_delete_response(self.server_b)

        MTPRotoKeyFactory(
            vds=self.server_a,
            expired_date=timezone.now() - timedelta(days=1),
        )

        get_remove_expired_keys_from_vds_infra_service()()

        self.assertEqual(len(responses.calls), 2)

    @responses.activate
    def test_marks_expired_keys_as_deleted_in_db(self) -> None:
        self._add_delete_response(self.server_a)
        self._add_delete_response(self.server_b)

        key = MTPRotoKeyFactory(
            vds=self.server_a,
            expired_date=timezone.now() - timedelta(days=1),
        )

        get_remove_expired_keys_from_vds_infra_service()()

        key.refresh_from_db()
        self.assertFalse(key.is_active)
        self.assertTrue(key.was_deleted)

    @responses.activate
    def test_cleans_expired_keys_from_all_home_servers(self) -> None:
        """Ключи с разных home-серверов чистятся в одном прогоне."""
        self._add_delete_response(self.server_a)
        self._add_delete_response(self.server_b)

        key_a = MTPRotoKeyFactory(vds=self.server_a, expired_date=timezone.now() - timedelta(days=1))
        key_b = MTPRotoKeyFactory(vds=self.server_b, expired_date=timezone.now() - timedelta(days=1))

        get_remove_expired_keys_from_vds_infra_service()()

        key_a.refresh_from_db()
        key_b.refresh_from_db()
        self.assertFalse(key_a.is_active)
        self.assertFalse(key_b.is_active)

    @mock.patch("apps.vds.services.remove_key_infra_service.RemoveUserKeyInfraService.__call__")
    def test_idempotent_on_second_call(self, infra_service) -> None:
        infra_service.return_value = None

        MTPRotoKeyFactory(
            vds=self.server_a,
            expired_date=timezone.now() - timedelta(days=1),
        )

        get_remove_expired_keys_from_vds_infra_service()()
        get_remove_expired_keys_from_vds_infra_service()()

        self.assertEqual(infra_service.call_count, 2)  # 2 сервера, 1 прогон
