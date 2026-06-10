from __future__ import annotations

import json
from unittest.mock import patch

import responses
from django.test import TestCase

from apps.vds.services.update_key_on_another_vds_infra_service import (
    get_update_key_on_another_vds_instances_service,
)
from apps.vds.tests.factories import VDSInstanceFactory


class TestUpdateKeyOnAnotherVdsInfraService(TestCase):
    def setUp(self) -> None:
        self.excluded = VDSInstanceFactory()
        self.target_1 = VDSInstanceFactory()
        self.target_2 = VDSInstanceFactory()

    def _mock_targets(self) -> None:
        for server in (self.target_1, self.target_2):
            responses.add(
                method=responses.PATCH,
                url=f"{server.internal_url}/api/users",
                json={"status": "ok"},
            )

    @responses.activate
    def test_patches_all_instances_except_excluded(self) -> None:
        responses.add(
            method=responses.PATCH,
            url=f"{self.excluded.internal_url}/api/users",
            json={"status": "ok"},
        )
        self._mock_targets()

        get_update_key_on_another_vds_instances_service()(
            exclude=self.excluded.pk,
            username="John",
            secret="test_secret",
        )

        called_urls = [call.request.url for call in responses.calls]
        self.assertEqual(len(responses.calls), 2)
        self.assertNotIn(f"{self.excluded.internal_url}/api/users", called_urls)

    @responses.activate
    def test_uses_patch_http_method(self) -> None:
        self._mock_targets()

        get_update_key_on_another_vds_instances_service()(
            exclude=self.excluded.pk,
            username="John",
            secret="test_secret",
        )

        for call in responses.calls:
            self.assertEqual(call.request.method, "PATCH")

    @responses.activate
    def test_sends_correct_payload(self) -> None:
        self._mock_targets()

        get_update_key_on_another_vds_instances_service()(
            exclude=self.excluded.pk,
            username="John",
            secret="test_secret",
        )

        for call in responses.calls:
            body = json.loads(call.request.body)
            self.assertEqual(body["username"], "John")
            self.assertEqual(body["secret"], "test_secret")

    @responses.activate
    def test_continues_on_http_error_and_notifies_admin(self) -> None:
        responses.add(
            method=responses.PATCH,
            url=f"{self.target_1.internal_url}/api/users",
            status=500,
        )
        responses.add(
            method=responses.PATCH,
            url=f"{self.target_2.internal_url}/api/users",
            json={"status": "ok"},
        )

        with patch(
            "apps.vds.services.update_key_on_another_vds_infra_service.send_telegram_message"
        ) as mock_send:
            get_update_key_on_another_vds_instances_service()(
                exclude=self.excluded.pk,
                username="John",
                secret="test_secret",
            )

        self.assertEqual(len(responses.calls), 2)
        mock_send.assert_called_once()
