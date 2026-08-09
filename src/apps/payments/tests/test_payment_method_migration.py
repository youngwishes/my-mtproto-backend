from __future__ import annotations

from decimal import Decimal
from importlib import import_module

from django.db import connection
from django.db.migrations import AddField
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


class TestPaymentMethodPriorityMigration(TransactionTestCase):
    migrate_from = ("payments", "0011_alter_cryptopaymentintent_options_and_more")
    migrate_to = ("payments", "0012_paymentmethod_is_priority")

    def setUp(self) -> None:
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        old_apps = self.executor.loader.project_state([self.migrate_from]).apps
        payment_method = old_apps.get_model("payments", "PaymentMethod")
        payment_method.objects.all().delete()
        payment_method.objects.create(
            code="stars",
            is_active=True,
            commission_percent=Decimal("0.00"),
        )
        payment_method.objects.create(
            code="crypto_pay",
            is_active=False,
            commission_percent=Decimal("17.25"),
        )

        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        self.apps = self.executor.loader.project_state([self.migrate_to]).apps

    def tearDown(self) -> None:
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_upgrade_preserves_existing_payment_method_values(self) -> None:
        payment_method = self.apps.get_model("payments", "PaymentMethod")

        self.assertEqual(
            list(
                payment_method.objects.order_by("code").values_list(
                    "code",
                    "is_active",
                    "commission_percent",
                    "is_priority",
                )
            ),
            [
                ("crypto_pay", False, Decimal("17.25"), False),
                ("stars", True, Decimal("0.00"), False),
            ],
        )

    def test_migration_contains_only_priority_add_field(self) -> None:
        migration = import_module(
            "apps.payments.migrations.0012_paymentmethod_is_priority"
        ).Migration

        self.assertEqual(migration.dependencies, [self.migrate_from])
        self.assertEqual(len(migration.operations), 1)
        operation = migration.operations[0]
        self.assertIsInstance(operation, AddField)
        self.assertEqual(operation.model_name, "paymentmethod")
        self.assertEqual(operation.name, "is_priority")
