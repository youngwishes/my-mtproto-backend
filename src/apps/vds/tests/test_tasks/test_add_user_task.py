import json

import responses
from django.test import TestCase

from apps.vds.models import VDSInstance

from apps.vds.tasks import add_key_to_another_vds_instances_task
from apps.vds.tests.factories import VDSInstanceFactory



class TestAddUserTask(TestCase):
    def setUp(self) -> None:
        self.vds = VDSInstanceFactory()
        for _ in range(5):
            VDSInstanceFactory()

    def _add_requests(self):
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
    def test_add_key_service(self) -> None:
        self._add_requests()
        add_key_to_another_vds_instances_task(exclude=self.vds.pk, username="John")
        self.assertEqual(len(responses.calls), 5)
        for call in responses.calls:
            self.assertTrue(call.request.url.endswith("/api/v1/add-new-user"))
            self.assertEqual(call.request.method, "POST")
            request_body = json.loads(call.request.body)
            self.assertEqual(request_body.get("username"), "John")
