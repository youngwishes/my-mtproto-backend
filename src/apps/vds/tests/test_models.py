from __future__ import annotations

from django.db import connection, models
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from apps.vds import models as vds_models
from apps.vds.models import VDSInstance
from apps.vds.tests.factories import MTPRotoKeyFactory


class TestVDSInstanceModelStructure(TestCase):
    def test_vds_instance_has_hosting_and_expired_at_fields(self) -> None:
        field_names = {field.name for field in VDSInstance._meta.get_fields()}

        self.assertTrue(hasattr(vds_models, "Hosting"))
        self.assertIn("hosting", field_names)
        self.assertIn("expired_at", field_names)

    def test_tls_domain_is_required_non_unique_and_has_no_default(self) -> None:
        field = VDSInstance._meta.get_field("tls_domain")

        self.assertFalse(field.blank)
        self.assertFalse(field.null)
        self.assertFalse(field.unique)
        self.assertIs(field.default, models.NOT_PROVIDED)


class TestMTPRotoKeyMethods(TestCase):
    def test_get_proxy_link_uses_given_server_name_and_tls_domain(self) -> None:
        key = MTPRotoKeyFactory(token="abc123")

        link = key.get_proxy_link(
            server_name="de1",
            tls_domain="тлс.example",
        )

        self.assertEqual(
            link,
            "tg://proxy?server=de1.mtprotokeys.com&port=443&secret="
            "eeabc123"
            "d182d0bb"
            "d1812e65"
            "78616d70"
            "6c65",
        )

    def test_different_tls_domains_change_only_client_secret(self) -> None:
        key = MTPRotoKeyFactory(token="abc123")

        first_secret = key.get_secret_token(tls_domain="tls-a.example")
        second_secret = key.get_secret_token(tls_domain="tls-b.example")

        self.assertEqual(
            first_secret,
            "eeabc123"
            "746c732d"
            "612e6578"
            "616d706c"
            "65",
        )
        self.assertEqual(
            second_secret,
            "eeabc123"
            "746c732d"
            "622e6578"
            "616d706c"
            "65",
        )
        self.assertNotEqual(first_secret, second_secret)
        self.assertEqual(key.token, "abc123")

    def test_tls_domain_does_not_change_proxy_host(self) -> None:
        key = MTPRotoKeyFactory(token="abc123")

        first_link = key.get_proxy_link(
            server_name="de1",
            tls_domain="tls-a.example",
        )
        second_link = key.get_proxy_link(
            server_name="de1",
            tls_domain="tls-b.example",
        )

        expected_prefix = "tg://proxy?server=de1.mtprotokeys.com&port=443&secret="
        self.assertTrue(first_link.startswith(expected_prefix))
        self.assertTrue(second_link.startswith(expected_prefix))

    def test_str_is_neutral(self) -> None:
        key = MTPRotoKeyFactory()
        self.assertEqual(str(key), f"MTPRotoKey #{key.pk} — {key.user_id}")


class TestVDSInstanceTLSDomainMigration(TransactionTestCase):
    migrate_from = ("vds", "0021_hosting_vdsinstance_expired_at_vdsinstance_hosting")
    migrate_to = ("vds", "0022_vdsinstance_tls_domain")

    def setUp(self) -> None:
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        old_apps = self.executor.loader.project_state([self.migrate_from]).apps
        old_vds_instance = old_apps.get_model("vds", "VDSInstance")
        self.vds_id = old_vds_instance.objects.create(
            name="existing",
            number=1,
            ip_address="192.0.2.1",
            internal_ip_address="192.0.2.2",
        ).pk

        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        self.apps = self.executor.loader.project_state([self.migrate_to]).apps

    def tearDown(self) -> None:
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_existing_vds_gets_tls_domain_without_model_default(self) -> None:
        vds_instance = self.apps.get_model("vds", "VDSInstance")
        migrated_vds = vds_instance.objects.get(pk=self.vds_id)

        self.assertEqual(migrated_vds.tls_domain, "mtprotokeys.com")
        self.assertIs(
            vds_instance._meta.get_field("tls_domain").default,
            models.NOT_PROVIDED,
        )
