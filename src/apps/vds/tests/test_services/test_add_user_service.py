import json
from unittest import mock

import responses
from django.test import TestCase

from apps.vds.models import VDSInstance
from apps.vds.services import (
    get_add_new_key_service_factory,
)
from apps.vds.services.exceptions import VDSConnectionLimit
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


@mock.patch("apps.core.bot.TelegramBot.log_infra_error")
@mock.patch("apps.core.bot.TelegramBot.send_sorry")
class TestAddUserService(TestCase):
    def setUp(self) -> None:
        self.vds = VDSInstanceFactory()
        for _ in range(5):
            VDSInstanceFactory()

    def _add_request(self):
        for server in VDSInstance.objects.all():
            responses.add(
                method=responses.POST,
                url=server.internal_url + "/api/v1/add-new-user",
                json={
                    "tls_domain": "petrovich.ru",
                    "key": "test",
                    "node_number": "telemt-node1",
                },
            )

    @responses.activate
    @mock.patch("apps.vds.services.add_new_key_infra_service.add_key_to_another_vds_instances_task")
    def test_add_key_service(self, add_to_other_servers, sorry, infra) -> None:
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
        self.assertEqual(infra.call_count, 0)
        self.assertEqual(sorry.call_count, 0)
        self.assertEqual(add_to_other_servers.delay.call_count, 1)

    def test_add_key_service_limit(self, sorry, infra) -> None:
        self._add_request()
        for _ in range(31):
            MTPRotoKeyFactory(vds=self.vds)
        with self.assertRaises(VDSConnectionLimit):
            get_add_new_key_service_factory()(
                username="-1003734483563", server=self.vds
            )
        self.assertEqual(len(responses.calls), 0)
        self.assertEqual(infra.call_count, 1)
        self.assertEqual(sorry.call_count, 1)
