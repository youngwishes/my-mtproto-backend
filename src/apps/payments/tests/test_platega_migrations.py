from __future__ import annotations

from decimal import Decimal
from importlib import import_module

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


platega_migration = import_module("apps.payments.migrations.0009_platega_payment_intent")
commission_migration = import_module(
    "apps.payments.migrations.0010_payment_method_commission"
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


class TestPaymentMethodCommissionMigration(TransactionTestCase):
    migrate_from = ("payments", "0009_platega_payment_intent")
    migrate_to = ("payments", "0010_payment_method_commission")

    def setUp(self) -> None:
        super().setUp()
        self.executor = MigrationExecutor(connection)

    def tearDown(self) -> None:
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.executor.loader.graph.leaf_nodes())
        super().tearDown()

    def _migrate(self, *, platega_active: bool | None):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        apps_before = self.executor.loader.project_state([self.migrate_from]).apps
        payment_method_before = apps_before.get_model("payments", "PaymentMethod")
        payment_method_before.objects.all().delete()
        payment_method_before.objects.create(code="stars", is_active=False)
        payment_method_before.objects.create(code="crypto_pay", is_active=True)
        if platega_active is not None:
            payment_method_before.objects.create(
                code="platega_sbp",
                is_active=platega_active,
            )

        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        return self.executor.loader.project_state([self.migrate_to]).apps.get_model(
            "payments", "PaymentMethod"
        )

    def test_sets_platega_commission_and_preserves_all_toggles(self) -> None:
        for platega_active in (True, False, None):
            with self.subTest(platega_active=platega_active):
                payment_method = self._migrate(platega_active=platega_active)

                platega = payment_method.objects.get(code="platega_sbp")
                self.assertEqual(platega.commission_percent, Decimal("8.00"))
                self.assertEqual(
                    platega.is_active,
                    False if platega_active is None else platega_active,
                )
                stars = payment_method.objects.get(code="stars")
                self.assertEqual(stars.commission_percent, Decimal("0.00"))
                self.assertFalse(stars.is_active)
                crypto = payment_method.objects.get(code="crypto_pay")
                self.assertEqual(crypto.commission_percent, Decimal("0.00"))
                self.assertTrue(crypto.is_active)

    def test_seed_updates_only_platega_commission(self) -> None:
        payment_method = self._migrate(platega_active=True)
        payment_method.objects.filter(code="platega_sbp").update(
            is_active=False,
            commission_percent=0,
        )

        apps = self.executor.loader.project_state([self.migrate_to]).apps
        commission_migration.seed_platega_commission(apps, None)

        platega = payment_method.objects.get(code="platega_sbp")
        self.assertFalse(platega.is_active)
        self.assertEqual(platega.commission_percent, Decimal("8.00"))
