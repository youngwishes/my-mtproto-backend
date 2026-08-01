from __future__ import annotations

import json
from unittest.mock import patch

import requests
import responses
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from django.test import SimpleTestCase

from apps.vpn.services.dtos import NodeProfileDTO
from apps.vpn.services.node_client_service import NodeClientService, get_node_client_service
from apps.vpn.tests.factories import VPNInstanceFactory


class TestNodeClientService(SimpleTestCase):
    def setUp(self) -> None:
        self.instance = VPNInstanceFactory.build(
            management_url="https://node.example.test/",
        )
        self.profile = NodeProfileDTO(
            access_id=42,
            vless_uuid="ee3a4b36-62e5-4c6a-8927-45eb8a5f72d1",
            hysteria_secret="hysteria-secret",
        )
        self.service = NodeClientService(agent_token="agent-token", timeout=5)

    @responses.activate
    def test_puts_profile_to_exact_agent_endpoint_with_bearer_credentials(self) -> None:
        responses.add(
            responses.PUT,
            "https://node.example.test/api/v1/profiles/42",
            status=204,
        )

        self.service.put_profile(instance=self.instance, profile=self.profile)

        self.assertEqual(len(responses.calls), 1)
        request = responses.calls[0].request
        self.assertEqual(request.headers["Authorization"], "Bearer agent-token")
        self.assertEqual(
            json.loads(request.body),
            {
                "vless_uuid": "ee3a4b36-62e5-4c6a-8927-45eb8a5f72d1",
                "hysteria_secret": "hysteria-secret",
            },
        )

    @responses.activate
    def test_deletes_profile_from_exact_agent_endpoint(self) -> None:
        responses.add(
            responses.DELETE,
            "https://node.example.test/api/v1/profiles/42",
            status=204,
        )

        self.service.delete_profile(instance=self.instance, access_id=42)

        self.assertEqual(len(responses.calls), 1)
        request = responses.calls[0].request
        self.assertEqual(request.headers["Authorization"], "Bearer agent-token")
        self.assertIsNone(request.body)

    @responses.activate
    def test_health_uses_exact_endpoint_and_accepts_any_2xx_response(self) -> None:
        responses.add(responses.GET, "https://node.example.test/health", status=204)

        self.service.check_health(instance=self.instance)

        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(
            responses.calls[0].request.headers["Authorization"],
            "Bearer agent-token",
        )

    @responses.activate
    def test_non_2xx_agent_response_is_not_treated_as_success(self) -> None:
        responses.add(
            responses.PUT,
            "https://node.example.test/api/v1/profiles/42",
            status=302,
        )

        with self.assertRaises(requests.HTTPError):
            self.service.put_profile(instance=self.instance, profile=self.profile)

    @responses.activate
    def test_does_not_follow_agent_redirect_as_a_successful_profile_delivery(self) -> None:
        responses.add(
            responses.PUT,
            "https://node.example.test/api/v1/profiles/42",
            headers={"Location": "https://redirected.example.test/profile"},
            status=302,
        )

        with self.assertRaises(requests.HTTPError):
            self.service.put_profile(instance=self.instance, profile=self.profile)

        self.assertEqual(len(responses.calls), 1)

    def test_uses_five_second_timeout_for_every_agent_request(self) -> None:
        with patch("apps.vpn.services.node_client_service.requests.put") as put:
            put.return_value.status_code = 200

            self.service.put_profile(instance=self.instance, profile=self.profile)

        self.assertEqual(put.call_args.kwargs["timeout"], 5)

    @override_settings(VPN_AGENT_TOKEN="")
    @patch("apps.vpn.services.node_client_service.requests.put")
    def test_factory_rejects_blank_agent_token_without_sending_request(self, put) -> None:
        with self.assertRaises(ImproperlyConfigured):
            get_node_client_service()

        put.assert_not_called()
