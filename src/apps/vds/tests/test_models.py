from __future__ import annotations

from django.conf import settings
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
    def test_get_proxy_link_uses_given_server_name_and_settings_tls_domain(self) -> None:
        key = MTPRotoKeyFactory(token="abc123")
        link = key.get_proxy_link(server_name="de1")
        domain_hex = settings.TLS_DOMAIN.encode("utf-8").hex()
        expected_secret = f"eeabc123{domain_hex}"
        self.assertEqual(
            link,
            f"tg://proxy?server=de1.beatvault.ru&port=443&secret={expected_secret}",
        )

    def test_get_secret_token_uses_settings_tls_domain_not_field(self) -> None:
        key = MTPRotoKeyFactory(token="abc123", tls_domain="ignored.example")
        domain_hex = settings.TLS_DOMAIN.encode("utf-8").hex()
        self.assertEqual(key.get_secret_token(), f"eeabc123{domain_hex}")

    def test_str_is_neutral(self) -> None:
        key = MTPRotoKeyFactory()
        self.assertEqual(str(key), f"MTPRotoKey #{key.pk} — {key.user_id}")
