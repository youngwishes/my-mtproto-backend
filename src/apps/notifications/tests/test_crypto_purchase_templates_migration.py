from __future__ import annotations

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class TestCryptoPurchaseTemplatesMigration(TransactionTestCase):
    migrate_from = ("notifications", "0010_seed_vpn_templates")
    migrate_to = ("notifications", "0011_seed_crypto_purchase_templates")

    def setUp(self) -> None:
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        old_apps = self.executor.loader.project_state([self.migrate_from]).apps
        template = old_apps.get_model("notifications", "NotificationTemplate")
        template.objects.update_or_create(
            slug="proxy_purchased",
            defaults={
                "title": "Stars result",
                "text": "Stars template must remain unchanged",
            },
        )
        template.objects.create(
            slug="crypto_vpn_purchased",
            title="Operator-owned VPN title",
            text="Operator-owned VPN text",
        )

        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        self.apps = self.executor.loader.project_state([self.migrate_to]).apps

    def tearDown(self) -> None:
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_adds_only_missing_crypto_result_templates(self) -> None:
        template = self.apps.get_model("notifications", "NotificationTemplate")

        self.assertEqual(
            template.objects.get(slug="crypto_vpn_purchased").text,
            "Operator-owned VPN text",
        )
        self.assertIn(
            "{code}",
            template.objects.get(
                slug="crypto_gift_certificate_purchased"
            ).text,
        )
        self.assertEqual(
            template.objects.get(slug="proxy_purchased").text,
            "Stars template must remain unchanged",
        )
