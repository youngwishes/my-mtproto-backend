from __future__ import annotations

import responses
from django.test import TestCase

from apps.vds.tests.factories import VDSInstanceFactory


class TestVdsHealthCheckInfraService(TestCase):
    def setUp(self) -> None:
        self.server = VDSInstanceFactory()

    def _get_service(self):
        from apps.vds.services.vds_health_check_infra_service import (
            get_vds_health_check_infra_service,
        )
        return get_vds_health_check_infra_service()

    @responses.activate
    def test_returns_true_when_server_responds(self) -> None:
        responses.add(
            method=responses.GET,
            url=self.server.internal_url,
            json={"status": "ok"},
        )

        result = self._get_service()(instance_id=self.server.pk)

        self.assertTrue(result)

    @responses.activate
    def test_returns_true_even_on_404_response(self) -> None:
        responses.add(
            method=responses.GET,
            url=self.server.internal_url,
            status=404,
        )

        result = self._get_service()(instance_id=self.server.pk)

        self.assertTrue(result)

    @responses.activate
    def test_returns_false_on_connection_error(self) -> None:
        responses.add(
            method=responses.GET,
            url=self.server.internal_url,
            body=ConnectionError("Connection refused"),
        )

        result = self._get_service()(instance_id=self.server.pk)

        self.assertFalse(result)
