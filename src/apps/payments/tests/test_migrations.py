from __future__ import annotations

import json
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class TestProductCodeVPNPaymentMigration(TransactionTestCase):
    migrate_from = ("payments", "0005_gift_certificates")
    migrate_to = ("payments", "0006_product_code_vpn_payment")

    def setUp(self) -> None:
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        old_apps = self.executor.loader.project_state([self.migrate_from]).apps
        old_product = old_apps.get_model("payments", "Product")
        old_product.objects.all().delete()
        self.existing_product = old_product.objects.create(
            title="Existing MTProto product",
            description="Existing product",
            provider_data="{}",
            price=99,
            stars_price=80,
        )

        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        self.apps = self.executor.loader.project_state([self.migrate_to]).apps

    def tearDown(self) -> None:
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_forward_migration_assigns_mtproto_code_and_creates_inactive_vpn_product(self) -> None:
        product = self.apps.get_model("payments", "Product")

        mtproto_product = product.objects.get(pk=self.existing_product.pk)
        vpn_product = product.objects.get(code="vpn_30d")

        self.assertEqual(mtproto_product.code, "mtproto_30d")
        self.assertFalse(vpn_product.is_active)
        self.assertEqual(vpn_product.price, Decimal("14900"))
        self.assertEqual(vpn_product.stars_price, 149)
        self.assertEqual(
            json.loads(vpn_product.provider_data)["items"][0]["amount"],
            {"value": 149, "currency": "RUB"},
        )

    def test_reverse_migration_removes_vpn_product_and_product_code(self) -> None:
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        old_apps = self.executor.loader.project_state([self.migrate_from]).apps
        product = old_apps.get_model("payments", "Product")

        self.assertNotIn("code", {field.name for field in product._meta.fields})
        self.assertEqual(product.objects.count(), 1)
        self.assertEqual(product.objects.get().title, "Existing MTProto product")
