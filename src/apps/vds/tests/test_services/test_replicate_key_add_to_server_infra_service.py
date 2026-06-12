from __future__ import annotations

import json

import responses
from django.test import TestCase

from apps.vds.tests.factories import VDSInstanceFactory


class TestReplicateKeyAddToServerInfraService(TestCase):
    def setUp(self) -> None:
        self.server = VDSInstanceFactory()

    def _get_service(self):
        from apps.vds.services.replicate_key_add_to_server_infra_service import (
            get_replicate_key_add_to_server_infra_service,
        )
        return get_replicate_key_add_to_server_infra_service()

    @responses.activate
    def test_posts_to_server_with_correct_payload(self) -> None:
        responses.add(
            method=responses.POST,
            url=f"{self.server.internal_url}/api/users",
            json={"status": "ok"},
        )

        self._get_service()(server_id=self.server.pk, username="john", secret="abc123")

        self.assertEqual(len(responses.calls), 1)
        body = json.loads(responses.calls[0].request.body)
        self.assertEqual(body["username"], "john")
        self.assertEqual(body["secret"], "abc123")
        self.assertEqual(responses.calls[0].request.method, "POST")

    @responses.activate
    def test_returns_silently_on_409(self) -> None:
        responses.add(
            method=responses.POST,
            url=f"{self.server.internal_url}/api/users",
            status=409,
            json={"detail": "already exists"},
        )

        # Should not raise
        self._get_service()(server_id=self.server.pk, username="john", secret="abc123")
        self.assertEqual(len(responses.calls), 1)

    @responses.activate
    def test_raises_on_server_error(self) -> None:
        responses.add(
            method=responses.POST,
            url=f"{self.server.internal_url}/api/users",
            status=500,
            json={"error": "internal server error"},
        )

        with self.assertRaises(Exception):
            self._get_service()(server_id=self.server.pk, username="john", secret="abc123")

    @responses.activate
    def test_raises_on_connection_error(self) -> None:
        responses.add(
            method=responses.POST,
            url=f"{self.server.internal_url}/api/users",
            body=ConnectionError("Connection refused"),
        )

        with self.assertRaises(Exception):
            self._get_service()(server_id=self.server.pk, username="john", secret="abc123")
