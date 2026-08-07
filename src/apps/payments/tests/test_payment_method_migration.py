from __future__ import annotations

from importlib import import_module

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


payment_method_migration = import_module(
    "apps.payments.migrations.0008_payment_method"
)


class TestPaymentMethodMigration(TransactionTestCase):
    migrate_from = ("payments", "0007_crypto_payment_intent")
    migrate_to = ("payments", "0008_payment_method")

    def setUp(self) -> None:
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])

        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        self.apps = self.executor.loader.project_state([self.migrate_to]).apps

    def tearDown(self) -> None:
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_seed_creates_active_rows_without_overwriting_saved_state(self) -> None:
        payment_method = self.apps.get_model("payments", "PaymentMethod")

        self.assertEqual(
            list(
                payment_method.objects.order_by("code").values_list(
                    "code", "is_active"
                )
            ),
            [("crypto_pay", True), ("stars", True)],
        )
        payment_method.objects.filter(code="crypto_pay").update(is_active=False)

        payment_method_migration.seed_payment_methods(self.apps, None)

        self.assertEqual(payment_method.objects.count(), 2)
        self.assertFalse(
            payment_method.objects.get(code="crypto_pay").is_active
        )
