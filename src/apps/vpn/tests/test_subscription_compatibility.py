from __future__ import annotations

import base64
import uuid
import json
from pathlib import Path

from django.test import SimpleTestCase

from apps.vpn.services.build_subscription import BuildVPNSubscriptionService
from apps.vpn.services.validate_subscription import ValidateVPNSubscriptionService
from apps.vpn.tests.factories import VPNNodeFactory


class VPNSubscriptionCompatibilityTest(SimpleTestCase):
    def test_generator_matches_pinned_v2rayn_import_fixture(self) -> None:
        fixture = json.loads(
            (Path(__file__).parent / "fixtures/v2rayn-7.24.0-vless-reality.json").read_text()
        )
        node = VPNNodeFactory.build(host="2001:db8::7", location="Test / IPv6")
        payload = BuildVPNSubscriptionService()(
            published_uuid=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
            nodes=(node,),
        )
        generated_uri = base64.b64decode(payload, validate=True).decode()
        self.assertEqual(generated_uri, fixture["accepted_uri"])
        parsed = ValidateVPNSubscriptionService()(payload=payload)[0]
        resolved = fixture["resolved"]
        self.assertEqual(str(parsed.uuid), resolved["password"])
        self.assertEqual(parsed.host, resolved["address"])
        self.assertEqual(parsed.port, resolved["port"])
        self.assertEqual(parsed.location, resolved["remarks"])

    def test_generated_fixture_passes_strict_supported_client_parser(self) -> None:
        node = VPNNodeFactory.build(host="2001:db8::7", location="Test / IPv6")
        payload = BuildVPNSubscriptionService()(
            published_uuid=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
            nodes=(node,),
        )
        links = ValidateVPNSubscriptionService()(payload=payload)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].host, "2001:db8::7")

    def test_rejects_noncanonical_base64_newline_and_wrong_profile(self) -> None:
        validator = ValidateVPNSubscriptionService()
        invalid_plaintexts = (
            b"not-a-vless-link",
            b"vless://aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa@example.com:443?encryption=none&flow=wrong&security=reality&sni=example.com&fp=chrome&pbk=k&sid=aa&type=tcp#Node",
            b"vless://aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa@example.com:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=example.com&fp=chrome&pbk=k&sid=aa&type=tcp#Node\n",
        )
        for plaintext in invalid_plaintexts:
            with self.subTest(plaintext=plaintext):
                with self.assertRaises(ValueError):
                    validator(payload=base64.b64encode(plaintext))
        with self.assertRaises(ValueError):
            validator(payload=b"%%%")
