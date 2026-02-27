import json

import responses
from django.test import TestCase

from apps.vds.services import (
    get_add_new_key_service_factory,
)
from apps.vds.tests.factories import VDSInstanceFactory


class TestAddUserService(TestCase):
    def setUp(self) -> None:
        self.vds = VDSInstanceFactory()

    def _add_request(self):
        responses.add(
            method=responses.POST,
            url=self.vds.url + "/api/v1/add-new-user",
            json={"tls_domain": "petrovich.ru", "key": "test"},
        )

    @responses.activate
    def test_add_key_service(self) -> None:
        self._add_request()
        get_add_new_key_service_factory()(username="John", server=self.vds)
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(
            responses.calls[0].request.url,
            self.vds.url + "/api/v1/add-new-user",
        )
        self.assertEqual(responses.calls[0].request.method, "POST")
        request_body = json.loads(responses.calls[0].request.body)
        self.assertEqual(request_body.get("username"), "John")
