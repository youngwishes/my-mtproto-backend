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
        self.instance = VDSInstanceFactory()

    def _add_delete_response(self, server=None) -> None:
        target = server or self.instance
        responses.add(
            method=responses.DELETE,
            url=target.internal_url + "/api/users",
        )

    @mock.patch("apps.vds.services.remove_key_infra_service.RemoveUserKeyInfraService.__call__")
    def test_no_expired_keys_exits_early(self, infra_service) -> None:
        MTPRotoKeyFactory(
            vds=self.instance,
            expired_date=timezone.now() + timedelta(days=1),
        )
        get_remove_expired_keys_from_vds_infra_service()(instance_id=self.instance.pk)
        self.assertEqual(infra_service.call_count, 0)

    @responses.activate
    def test_removes_expired_key_from_all_vds_servers(self) -> None:
        other = VDSInstanceFactory()
        self._add_delete_response(server=self.instance)
        self._add_delete_response(server=other)

        MTPRotoKeyFactory(
            vds=self.instance,
            expired_date=timezone.now() - timedelta(days=1),
        )

        get_remove_expired_keys_from_vds_infra_service()(instance_id=self.instance.pk)

        self.assertEqual(len(responses.calls), 2)

    @responses.activate
    def test_marks_expired_keys_as_deleted_in_db(self) -> None:
        self._add_delete_response()
        key = MTPRotoKeyFactory(
            vds=self.instance,
            expired_date=timezone.now() - timedelta(days=1),
        )

        get_remove_expired_keys_from_vds_infra_service()(instance_id=self.instance.pk)

        key.refresh_from_db()
        self.assertFalse(key.is_active)
        self.assertTrue(key.was_deleted)

    @responses.activate
    def test_does_not_touch_keys_on_other_instances(self) -> None:
        other_instance = VDSInstanceFactory()
        self._add_delete_response()
        key_other = MTPRotoKeyFactory(
            vds=other_instance,
            expired_date=timezone.now() - timedelta(days=1),
        )

        get_remove_expired_keys_from_vds_infra_service()(instance_id=self.instance.pk)

        key_other.refresh_from_db()
        self.assertTrue(key_other.is_active)
        self.assertFalse(key_other.was_deleted)

    @mock.patch("apps.vds.services.remove_key_infra_service.RemoveUserKeyInfraService.__call__")
    def test_idempotent_on_second_call(self, infra_service) -> None:
        key = MTPRotoKeyFactory(
            vds=self.instance,
            expired_date=timezone.now() - timedelta(days=1),
        )
        infra_service.return_value = None

        get_remove_expired_keys_from_vds_infra_service()(instance_id=self.instance.pk)
        get_remove_expired_keys_from_vds_infra_service()(instance_id=self.instance.pk)

        # второй вызов не должен обрабатывать уже удалённый ключ
        self.assertEqual(infra_service.call_count, 1)
