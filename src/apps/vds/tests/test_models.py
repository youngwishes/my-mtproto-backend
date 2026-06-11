from __future__ import annotations

from django.test import TestCase

from apps.vds.selectors import get_least_populated_vds
from apps.vds.tests.factories import MTPRotoKeyFactory, VDSInstanceFactory


class TestVDSQuerySet(TestCase):
    def test_get_least_populated_excludes_is_keys_available_false(self) -> None:
        VDSInstanceFactory(is_keys_available=False)
        available = VDSInstanceFactory(is_keys_available=True)

        result = get_least_populated_vds()

        self.assertEqual(result, available)

    def test_get_least_populated_picks_least_loaded_among_available(self) -> None:
        server_1 = VDSInstanceFactory(is_keys_available=True)
        server_2 = VDSInstanceFactory(is_keys_available=True)
        for _ in range(3):
            MTPRotoKeyFactory(vds=server_1)

        result = get_least_populated_vds()

        self.assertEqual(result, server_2)

    def test_get_least_populated_returns_none_when_all_have_keys_unavailable(self) -> None:
        VDSInstanceFactory(is_keys_available=False)

        result = get_least_populated_vds()

        self.assertIsNone(result)


class TestMTPRotoKeyMethods(TestCase):
    def test_get_proxy_link_for_server_uses_given_server_name(self) -> None:
        key = MTPRotoKeyFactory(
            token="abc123",
            tls_domain="petrovich.ru",
        )
        link = key.get_proxy_link_for_server("de1")
        domain_hex = "petrovich.ru".encode("utf-8").hex()
        expected_secret = f"eeabc123{domain_hex}"
        self.assertEqual(
            link,
            f"tg://proxy?server=de1.beatvault.ru&port=443&secret={expected_secret}",
        )

    def test_get_proxy_link_for_server_differs_from_primary(self) -> None:
        key = MTPRotoKeyFactory(
            token="abc123",
            tls_domain="petrovich.ru",
            node_number="nl1",
        )
        primary_link = key.get_proxy_link()
        replica_link = key.get_proxy_link_for_server("de1")
        self.assertNotEqual(primary_link, replica_link)
        self.assertIn("nl1.beatvault.ru", primary_link)
        self.assertIn("de1.beatvault.ru", replica_link)
