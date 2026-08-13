from __future__ import annotations

from django.conf import settings
from django.test import TestCase

from apps.vds import models as vds_models
from apps.vds.models import VDSInstance
from apps.vds.tests.factories import MTPRotoKeyFactory


class TestVDSInstanceModelStructure(TestCase):
    def test_vds_instance_has_hosting_and_expired_at_fields(self) -> None:
        field_names = {field.name for field in VDSInstance._meta.get_fields()}

        self.assertTrue(hasattr(vds_models, "Hosting"))
        self.assertIn("hosting", field_names)
        self.assertIn("expired_at", field_names)


class TestMTPRotoKeyMethods(TestCase):
    def test_get_proxy_link_uses_given_server_name_and_settings_tls_domain(self) -> None:
        key = MTPRotoKeyFactory(token="abc123")
        link = key.get_proxy_link(server_name="de1")
        domain_hex = settings.TLS_DOMAIN.encode("utf-8").hex()
        expected_secret = f"eeabc123{domain_hex}"
        self.assertEqual(
            link,
            f"tg://proxy?server=de1.mtprotokeys.com&port=443&secret={expected_secret}",
        )

    def test_get_secret_token_uses_settings_tls_domain(self) -> None:
        key = MTPRotoKeyFactory(token="abc123")
        domain_hex = settings.TLS_DOMAIN.encode("utf-8").hex()
        self.assertEqual(key.get_secret_token(), f"eeabc123{domain_hex}")

    def test_str_is_neutral(self) -> None:
        key = MTPRotoKeyFactory()
        self.assertEqual(str(key), f"MTPRotoKey #{key.pk} — {key.user_id}")
