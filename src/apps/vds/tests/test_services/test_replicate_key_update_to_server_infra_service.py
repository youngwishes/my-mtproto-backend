from __future__ import annotations

import json

import responses
from django.test import TestCase

from apps.vds.tests.factories import VDSInstanceFactory


class TestReplicateKeyUpdateToServerInfraService(TestCase):
    def setUp(self) -> None:
        self.server = VDSInstanceFactory()

    def _get_service(self):
        from apps.vds.services.replicate_key_update_to_server_infra_service import (
            get_replicate_key_update_to_server_infra_service,
        )
        return get_replicate_key_update_to_server_infra_service()

    @responses.activate
    def test_patches_server_with_correct_payload(self) -> None:
        responses.add(
            method=responses.PATCH,
            url=f"{self.server.internal_url}/api/users",
            json={"status": "ok"},
        )

        self._get_service()(server_id=self.server.pk, username="john", secret="abc123")

        self.assertEqual(len(responses.calls), 1)
        body = json.loads(responses.calls[0].request.body)
        self.assertEqual(body["username"], "john")
        self.assertEqual(body["secret"], "abc123")
        self.assertEqual(responses.calls[0].request.method, "PATCH")

    @responses.activate
    def test_falls_back_to_post_on_404(self) -> None:
        responses.add(
            method=responses.PATCH,
            url=f"{self.server.internal_url}/api/users",
            status=404,
            json={"detail": "not found"},
        )
        responses.add(
            method=responses.POST,
            url=f"{self.server.internal_url}/api/users",
            json={"status": "ok"},
        )

        self._get_service()(server_id=self.server.pk, username="john", secret="abc123")

        self.assertEqual(len(responses.calls), 2)
        self.assertEqual(responses.calls[0].request.method, "PATCH")
        self.assertEqual(responses.calls[1].request.method, "POST")
        post_body = json.loads(responses.calls[1].request.body)
        self.assertEqual(post_body["secret"], "abc123")

    @responses.activate
    def test_raises_on_server_error(self) -> None:
        responses.add(
            method=responses.PATCH,
            url=f"{self.server.internal_url}/api/users",
            status=500,
        )

        with self.assertRaises(Exception):
            self._get_service()(server_id=self.server.pk, username="john", secret="abc123")

    @responses.activate
    def test_raises_on_connection_error(self) -> None:
        responses.add(
            method=responses.PATCH,
            url=f"{self.server.internal_url}/api/users",
            body=ConnectionError("Connection refused"),
        )

        with self.assertRaises(Exception):
            self._get_service()(server_id=self.server.pk, username="john", secret="abc123")
