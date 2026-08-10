from __future__ import annotations

from base64 import b64decode

from django.test import TestCase

from apps.vpn.services import BuildSubscriptionService
from apps.vpn.tests.factories import VPNInstanceFactory, VPNSubscriptionFactory


class TestBuildSubscriptionService(TestCase):
    def test_builds_two_percent_encoded_uris_per_instance_in_deterministic_order(self) -> None:
        obfs_query_name = "obfs-" + "password"
        subscription = VPNSubscriptionFactory(
            vless_uuid="11111111-2222-3333-4444-555555555555",
            hysteria_secret="secret /@?",
        )
        second = VPNInstanceFactory(
            number=20,
            name="Second node",
            public_host="second.example.com",
            hysteria_obfs="second fixture",
        )
        first = VPNInstanceFactory(
            number=10,
            name="Moscow & One",
            public_host="first.example.com",
            reality_sni="reality sni/?",
            reality_public_key="Key+/=",
            reality_short_id="a/b",
            hysteria_sni="hysteria sni",
            hysteria_obfs="fixture value/?",
        )

        def sort_nodes_by_number(instances: list[object]) -> None:
            instances.sort(key=lambda instance: (instance.number, instance.pk))

        content = BuildSubscriptionService(shuffle_nodes=sort_nodes_by_number)(
            instances=[second, first],
            subscription=subscription,
        )

        decoded = b64decode(content).decode("utf-8")
        self.assertEqual(
            decoded,
            "\n".join(
                [
                    "vless://11111111-2222-3333-4444-555555555555@first.example.com:443?"
                    "encryption=none&flow=xtls-rprx-vision&security=reality&"
                    "sni=reality%20sni%2F%3F&fp=chrome&pbk=Key%2B%2F%3D&sid=a%2Fb&"
                    "type=tcp#Moscow%20%26%20One%20VLESS",
                    "hysteria2://secret%20%2F%40%3F@first.example.com:443/?"
                    f"sni=hysteria%20sni&obfs=salamander&{obfs_query_name}="
                    "fixture%20value%2F%3F#"
                    "Moscow%20%26%20One%20Hysteria2",
                    "vless://11111111-2222-3333-4444-555555555555@second.example.com:443?"
                    "encryption=none&flow=xtls-rprx-vision&security=reality&"
                    "sni=www.example.com&fp=chrome&pbk=public-key&sid=short-id&"
                    "type=tcp#Second%20node%20VLESS",
                    "hysteria2://secret%20%2F%40%3F@second.example.com:443/?"
                    f"sni=www.example.com&obfs=salamander&{obfs_query_name}="
                    "second%20fixture#"
                    "Second%20node%20Hysteria2",
                ]
            ),
        )
        self.assertEqual(len(decoded.splitlines()), 4)

    def test_allows_deterministic_node_block_reordering_via_injected_shuffler(self) -> None:
        subscription = VPNSubscriptionFactory(
            vless_uuid="11111111-2222-3333-4444-555555555555",
            hysteria_secret="hysteria-secret",
        )
        first = VPNInstanceFactory(number=10, name="First node", public_host="first.example.com")
        second = VPNInstanceFactory(number=20, name="Second node", public_host="second.example.com")

        def reverse_nodes(instances: list[object]) -> None:
            instances.reverse()

        self.assertIn("shuffle_nodes", BuildSubscriptionService.__dataclass_fields__)

        content = BuildSubscriptionService(shuffle_nodes=reverse_nodes)(
            instances=[first, second],
            subscription=subscription,
        )

        decoded = b64decode(content).decode("utf-8").splitlines()
        self.assertEqual(
            decoded,
            [
                "vless://11111111-2222-3333-4444-555555555555@second.example.com:443?"
                "encryption=none&flow=xtls-rprx-vision&security=reality&"
                "sni=www.example.com&fp=chrome&pbk=public-key&sid=short-id&"
                "type=tcp#Second%20node%20VLESS",
                "hysteria2://hysteria-secret@second.example.com:443/?"
                "sni=www.example.com&obfs=salamander&obfs-password=obfs-password#"
                "Second%20node%20Hysteria2",
                "vless://11111111-2222-3333-4444-555555555555@first.example.com:443?"
                "encryption=none&flow=xtls-rprx-vision&security=reality&"
                "sni=www.example.com&fp=chrome&pbk=public-key&sid=short-id&"
                "type=tcp#First%20node%20VLESS",
                "hysteria2://hysteria-secret@first.example.com:443/?"
                "sni=www.example.com&obfs=salamander&obfs-password=obfs-password#"
                "First%20node%20Hysteria2",
            ],
        )
