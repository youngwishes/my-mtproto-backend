from __future__ import annotations

import base64
import uuid
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.vpn.services.build_subscription import BuildVPNSubscriptionService


class BuildVPNSubscriptionServiceTest(SimpleTestCase):
    def test_builds_ordered_reality_links_with_public_parameters(self) -> None:
        published_uuid = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        nodes = (
            SimpleNamespace(number=2, location="Location 2", host="2001:db8::2", port=443,
                            reality_public_key="public_key-2", reality_short_id="cdef",
                            reality_server_name="two.example.com", reality_fingerprint="chrome",
                            reality_flow="xtls-rprx-vision"),
            SimpleNamespace(number=1, location="Location 1", host="one.example.com", port=8443,
                            reality_public_key="public_key-1", reality_short_id="abcd",
                            reality_server_name="one.example.com", reality_fingerprint="chrome",
                            reality_flow="xtls-rprx-vision"),
        )

        encoded = BuildVPNSubscriptionService()(published_uuid=published_uuid, nodes=nodes)

        plaintext = base64.b64decode(encoded).decode()
        self.assertEqual(
            plaintext.splitlines(),
            [
                "vless://aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa@one.example.com:8443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=one.example.com&fp=chrome&pbk=public_key-1&sid=abcd&type=tcp#Location%201",
                "vless://aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa@[2001:db8::2]:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=two.example.com&fp=chrome&pbk=public_key-2&sid=cdef&type=tcp#Location%202",
            ],
        )
        self.assertFalse(plaintext.endswith("\n"))

    def test_empty_nodes_return_empty_base64_payload(self) -> None:
        self.assertEqual(
            BuildVPNSubscriptionService()(
                published_uuid=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
                nodes=(),
            ),
            b"",
        )
