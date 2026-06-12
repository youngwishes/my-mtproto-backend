import json
from unittest import mock

import responses
from django.test import TestCase

from apps.vds.models import VDSInstance
from apps.vds.services import (
    get_add_new_key_service_factory,
)
from apps.vds.exceptions import VDSConnectionLimit
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


@mock.patch("apps.notifications.services.send_notification_service.send_telegram_message")
@mock.patch("apps.core.decorators._log_infra_error")
class TestAddUserService(TestCase):
    def setUp(self) -> None:
        self.vds = VDSInstanceFactory()
        for _ in range(5):
            VDSInstanceFactory()

    def _add_request(self):
        for server in VDSInstance.objects.all():
            responses.add(
                method=responses.POST,
                url=server.internal_url + "/api/users",
                json={
                    "tls_domain": "petrovich.ru",
                    "key": "test",
                },
            )

    @responses.activate
    @mock.patch("apps.vds.services.add_new_key_infra_service.add_key_to_another_vds_instances_task")
    def test_add_key_service(self, add_to_other_servers, infra, mock_send) -> None:
        self._add_request()
        get_add_new_key_service_factory()(username="John", server=self.vds)
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(
            responses.calls[0].request.url,
            self.vds.internal_url + "/api/users",
        )
        self.assertEqual(responses.calls[0].request.method, "POST")
        request_body = json.loads(responses.calls[0].request.body)
        self.assertEqual(request_body.get("username"), "John")
        self.assertEqual(infra.call_count, 0)
        self.assertEqual(add_to_other_servers.delay.call_count, 1)

    @responses.activate
    @mock.patch("apps.vds.services.add_new_key_infra_service.add_key_to_another_vds_instances_task")
    def test_falls_back_to_patch_when_post_returns_409(self, add_to_other_servers, infra, mock_send) -> None:
        responses.add(
            method=responses.POST,
            url=f"{self.vds.internal_url}/api/users",
            status=409,
            json={"detail": "User already exists"},
        )
        responses.add(
            method=responses.PATCH,
            url=f"{self.vds.internal_url}/api/users",
            json={"key": "healed_key", "tls_domain": "healed.domain"},
        )

        result = get_add_new_key_service_factory()(username="John", server=self.vds)

        self.assertEqual(len(responses.calls), 2)
        self.assertEqual(responses.calls[0].request.method, "POST")
        self.assertEqual(responses.calls[1].request.method, "PATCH")
        self.assertEqual(result.key, "healed_key")
        self.assertEqual(result.tls_domain, "healed.domain")

    @responses.activate
    @mock.patch("apps.vds.services.add_new_key_infra_service.add_key_to_another_vds_instances_task")
    def test_patch_fallback_uses_same_secret_as_post(self, add_to_other_servers, infra, mock_send) -> None:
        responses.add(
            method=responses.POST,
            url=f"{self.vds.internal_url}/api/users",
            status=409,
            json={"detail": "User already exists"},
        )
        responses.add(
            method=responses.PATCH,
            url=f"{self.vds.internal_url}/api/users",
            json={"key": "healed_key", "tls_domain": "healed.domain"},
        )

        get_add_new_key_service_factory()(username="John", server=self.vds)

        post_secret = json.loads(responses.calls[0].request.body)["secret"]
        patch_secret = json.loads(responses.calls[1].request.body)["secret"]
        self.assertEqual(post_secret, patch_secret)

    @responses.activate
    @mock.patch("apps.vds.services.add_new_key_infra_service.add_key_to_another_vds_instances_task")
    def test_dispatches_replication_task_on_409_fallback(self, add_to_other_servers, infra, mock_send) -> None:
        responses.add(
            method=responses.POST,
            url=f"{self.vds.internal_url}/api/users",
            status=409,
            json={"detail": "User already exists"},
        )
        responses.add(
            method=responses.PATCH,
            url=f"{self.vds.internal_url}/api/users",
            json={"key": "healed_key", "tls_domain": "healed.domain"},
        )

        get_add_new_key_service_factory()(username="John", server=self.vds)

        add_to_other_servers.delay.assert_called_once_with(
            exclude=self.vds.pk,
            username="John",
            secret=mock.ANY,
        )

    def test_add_key_service_limit(self, infra, mock_send) -> None:
        self._add_request()
        for _ in range(31):
            MTPRotoKeyFactory(vds=self.vds)
        with self.assertRaises(VDSConnectionLimit):
            get_add_new_key_service_factory()(
                username="-1003734483563", server=self.vds
            )
        self.assertEqual(len(responses.calls), 0)
        self.assertEqual(infra.call_count, 1)
