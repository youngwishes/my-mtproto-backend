from __future__ import annotations

import json
from unittest.mock import patch

import responses
from django.test import TestCase

from apps.vds.services import get_remove_keys_from_vds_instance_infra_service
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestRemoveKeysFromVdsInstanceInfraService(TestCase):
    def setUp(self) -> None:
        self.server = VDSInstanceFactory()
        self.key_1 = MTPRotoKeyFactory()
        self.key_2 = MTPRotoKeyFactory()

    @responses.activate
    def test_sends_delete_request_to_correct_server(self) -> None:
        responses.add(
            method=responses.DELETE,
            url=f"{self.server.internal_url}/api/users",
            json={"status": "ok"},
        )

        get_remove_keys_from_vds_instance_infra_service()(
            server_id=self.server.pk,
            keys_ids=[self.key_1.pk, self.key_2.pk],
        )

        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(
            responses.calls[0].request.url,
            f"{self.server.internal_url}/api/users",
        )

    @responses.activate
    def test_sends_correct_usernames_payload(self) -> None:
        responses.add(
            method=responses.DELETE,
            url=f"{self.server.internal_url}/api/users",
            json={"status": "ok"},
        )

        get_remove_keys_from_vds_instance_infra_service()(
            server_id=self.server.pk,
            keys_ids=[self.key_1.pk, self.key_2.pk],
        )

        body = json.loads(responses.calls[0].request.body)
        self.assertCountEqual(
            body["usernames"],
            [self.key_1.user.username, self.key_2.user.username],
        )

    @responses.activate
    def test_marks_keys_as_deleted_on_success(self) -> None:
        responses.add(
            method=responses.DELETE,
            url=f"{self.server.internal_url}/api/users",
            json={"status": "ok"},
        )

        get_remove_keys_from_vds_instance_infra_service()(
            server_id=self.server.pk,
            keys_ids=[self.key_1.pk, self.key_2.pk],
        )

        self.key_1.refresh_from_db()
        self.key_2.refresh_from_db()
        self.assertTrue(self.key_1.was_deleted)
        self.assertFalse(self.key_1.is_active)
        self.assertTrue(self.key_2.was_deleted)
        self.assertFalse(self.key_2.is_active)

    @responses.activate
    def test_notifies_admin_on_http_error_and_does_not_update_keys(self) -> None:
        responses.add(
            method=responses.DELETE,
            url=f"{self.server.internal_url}/api/users",
            json={"error": "fail"},
            status=500,
        )

        with patch(
            "apps.vds.services.remove_keys_from_vds_instance_infra_service.send_telegram_message"
        ) as mock_send:
            get_remove_keys_from_vds_instance_infra_service()(
                server_id=self.server.pk,
                keys_ids=[self.key_1.pk, self.key_2.pk],
            )

        mock_send.assert_called_once()
        self.key_1.refresh_from_db()
        self.key_2.refresh_from_db()
        self.assertFalse(self.key_1.was_deleted)
        self.assertTrue(self.key_1.is_active)
        self.assertFalse(self.key_2.was_deleted)
        self.assertTrue(self.key_2.is_active)
