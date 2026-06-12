from __future__ import annotations

import json
from unittest.mock import patch

import responses
from django.test import TestCase

from apps.vds.services import get_add_key_to_another_vds_instances_service
from apps.vds.tests.factories import VDSInstanceFactory


class TestAddKeyToAnotherVdsInfraService(TestCase):
    def setUp(self) -> None:
        self.excluded = VDSInstanceFactory()
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
    def test_posts_to_all_instances_except_excluded(self) -> None:
        responses.add(
            method=responses.POST,
            url=f"{self.excluded.internal_url}/api/users",
            json={"status": "ok"},
        )
        self._mock_target_endpoints()

        get_add_key_to_another_vds_instances_service()(
            exclude=self.excluded.pk,
            username="John",
            secret="test_secret",
        )

        called_urls = [call.request.url for call in responses.calls]
        self.assertEqual(len(responses.calls), 2)
        self.assertNotIn(f"{self.excluded.internal_url}/api/users", called_urls)

    @responses.activate
    def test_sends_correct_payload(self) -> None:
        self._mock_target_endpoints()

        get_add_key_to_another_vds_instances_service()(
            exclude=self.excluded.pk,
            username="John",
            secret="test_secret",
        )

        for call in responses.calls:
            body = json.loads(call.request.body)
            self.assertEqual(body["username"], "John")
            self.assertEqual(body["secret"], "test_secret")

    @responses.activate
    def test_silently_skips_409_without_admin_notification(self) -> None:
        responses.add(
            method=responses.POST,
            url=f"{self.target_1.internal_url}/api/users",
            status=409,
            json={"detail": "User already exists"},
        )
        responses.add(
            method=responses.POST,
            url=f"{self.target_2.internal_url}/api/users",
            json={"status": "ok"},
        )

        with patch("apps.vds.services.add_key_to_another_vds_infra_service.send_telegram_message") as mock_send:
            get_add_key_to_another_vds_instances_service()(
                exclude=self.excluded.pk,
                username="John",
                secret="test_secret",
            )

        mock_send.assert_not_called()
        self.assertEqual(len(responses.calls), 2)

    @responses.activate
    def test_continues_on_http_error_and_notifies_admin(self) -> None:
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

        with patch("apps.vds.services.add_key_to_another_vds_infra_service.send_telegram_message") as mock_send:
            get_add_key_to_another_vds_instances_service()(
                exclude=self.excluded.pk,
                username="John",
                secret="test_secret",
            )

        self.assertEqual(len(responses.calls), 2)
        mock_send.assert_called_once()
