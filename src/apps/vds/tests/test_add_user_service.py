import json

import responses
from django.test import TestCase

from apps.vds.services import (
    get_add_new_key_service_factory,
)
from apps.vds.services.exceptions import VDSConnectionLimit
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestAddUserService(TestCase):
    def setUp(self) -> None:
        self.vds = VDSInstanceFactory()

    def _add_request(self):
        responses.add(
            method=responses.POST,
            url=self.vds.internal_url + "/api/v1/add-new-user",
            json={"tls_domain": "petrovich.ru", "key": "test"},
        )

    @responses.activate
    def test_add_key_service(self) -> None:
        self._add_request()
        get_add_new_key_service_factory()(username="John", server=self.vds)
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(
            responses.calls[0].request.url,
            self.vds.internal_url + "/api/v1/add-new-user",
        )
        self.assertEqual(responses.calls[0].request.method, "POST")
        request_body = json.loads(responses.calls[0].request.body)
        self.assertEqual(request_body.get("username"), "John")

    def test_add_key_service_limit(self) -> None:
        self._add_request()
        for _ in range(31):
            MTPRotoKeyFactory(vds=self.vds)
        with self.assertRaises(VDSConnectionLimit):
            get_add_new_key_service_factory()(username="-1003734483563", server=self.vds)
        self.assertEqual(len(responses.calls), 0)
