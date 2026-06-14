from __future__ import annotations

from datetime import timedelta
from unittest import mock

import responses
from django.test import TestCase
from django.utils import timezone

from apps.vds.services.remove_dead_keys_from_vds_infra_service import (
    get_remove_dead_keys_from_vds_infra_service,
)
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestRemoveDeadKeysFromVdsInfraService(TestCase):
    def setUp(self) -> None:
        self.server_a = VDSInstanceFactory()
        self.server_b = VDSInstanceFactory()

    def _add_delete_response(self, server) -> None:
        responses.add(
            method=responses.DELETE,
            url=server.internal_url + "/api/users",
        )

    @mock.patch("apps.vds.services.remove_key_infra_service.RemoveUserKeyInfraService.__call__")
    def test_no_dead_keys_exits_early(self, infra_service) -> None:
        MTPRotoKeyFactory(is_active=True, was_deleted=False)
        get_remove_dead_keys_from_vds_infra_service()(instance_id=self.server_a.pk)
        self.assertEqual(infra_service.call_count, 0)

    @responses.activate
    def test_sends_delete_only_to_selected_server(self) -> None:
        self._add_delete_response(self.server_a)
        MTPRotoKeyFactory(
            is_active=False,
            was_deleted=True,
            expired_date=timezone.now() - timedelta(days=1),
        )

        get_remove_dead_keys_from_vds_infra_service()(instance_id=self.server_a.pk)

        self.assertEqual(len(responses.calls), 1)
        self.assertIn(self.server_a.internal_url, responses.calls[0].request.url)

    @responses.activate
    def test_does_not_send_to_other_servers(self) -> None:
        self._add_delete_response(self.server_a)
        self._add_delete_response(self.server_b)
        MTPRotoKeyFactory(
            is_active=False,
            was_deleted=True,
            expired_date=timezone.now() - timedelta(days=1),
        )

        get_remove_dead_keys_from_vds_infra_service()(instance_id=self.server_a.pk)

        called_urls = [call.request.url for call in responses.calls]
        self.assertNotIn(self.server_b.internal_url + "/api/users", called_urls)
        self.assertEqual(len(responses.calls), 1)

    @mock.patch("apps.vds.services.remove_key_infra_service.RemoveUserKeyInfraService.__call__")
    def test_does_not_touch_active_keys(self, infra_service) -> None:
        MTPRotoKeyFactory(is_active=True, was_deleted=False)
        get_remove_dead_keys_from_vds_infra_service()(instance_id=self.server_a.pk)
        self.assertEqual(infra_service.call_count, 0)

    @mock.patch("apps.vds.services.remove_key_infra_service.RemoveUserKeyInfraService.__call__")
    def test_excludes_dead_keys_with_future_expiry(self, infra_service) -> None:
        MTPRotoKeyFactory(
            is_active=False,
            was_deleted=True,
            expired_date=timezone.now() + timedelta(days=1),
        )
        get_remove_dead_keys_from_vds_infra_service()(instance_id=self.server_a.pk)
        self.assertEqual(infra_service.call_count, 0)

    @mock.patch("apps.vds.services.remove_key_infra_service.RemoveUserKeyInfraService.__call__")
    def test_does_not_update_db_state(self, infra_service) -> None:
        infra_service.return_value = None
        key = MTPRotoKeyFactory(
            is_active=False,
            was_deleted=True,
            expired_date=timezone.now() - timedelta(days=1),
        )

        get_remove_dead_keys_from_vds_infra_service()(instance_id=self.server_a.pk)

        key.refresh_from_db()
        self.assertFalse(key.is_active)
        self.assertTrue(key.was_deleted)
