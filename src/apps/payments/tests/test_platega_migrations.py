from __future__ import annotations

from importlib import import_module

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


platega_migration = import_module(
    "apps.payments.migrations.0009_platega_payment_intent"
)


class TestPlategaPaymentIntentMigration(TransactionTestCase):
    migrate_from = ("payments", "0008_payment_method")
    migrate_to = ("payments", "0009_platega_payment_intent")

    def setUp(self) -> None:
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        self.apps_before = self.executor.loader.project_state([self.migrate_from]).apps
        payment_method_before = self.apps_before.get_model("payments", "PaymentMethod")
        payment_method_before.objects.all().delete()
        payment_method_before.objects.create(
            code="platega_sbp",
            is_active=True,
        )

        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        self.apps = self.executor.loader.project_state([self.migrate_to]).apps

    def tearDown(self) -> None:
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_seed_is_additive_and_never_overwrites_saved_toggle_state(self) -> None:
        payment_method = self.apps.get_model("payments", "PaymentMethod")

        self.assertTrue(payment_method.objects.get(code="platega_sbp").is_active)
        payment_method.objects.filter(code="platega_sbp").update(is_active=False)

        platega_migration.seed_platega_payment_method(self.apps, None)

        self.assertEqual(payment_method.objects.filter(code="platega_sbp").count(), 1)
        self.assertFalse(payment_method.objects.get(code="platega_sbp").is_active)

    def test_seed_creates_inactive_toggle_when_no_legacy_row_exists(self) -> None:
        payment_method = self.apps.get_model("payments", "PaymentMethod")
        payment_method.objects.filter(code="platega_sbp").delete()

        platega_migration.seed_platega_payment_method(self.apps, None)

        self.assertFalse(payment_method.objects.get(code="platega_sbp").is_active)
