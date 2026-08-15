from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import migrations, models
from django.db.migrations.loader import MigrationLoader
from django.test import SimpleTestCase


class ProjectServerInitialMigrationTest(SimpleTestCase):
    migration_key = ("infrastructure", "0001_initial")

    def setUp(self) -> None:
        loader = MigrationLoader(None, load=False)
        loader.load_disk()
        self.migration = loader.disk_migrations[self.migration_key]

    def test_initial_migration_is_discoverable_with_exact_dependency(self) -> None:
        self.assertTrue(self.migration.initial)
        self.assertEqual(
            self.migration.dependencies,
            [("vds", "0021_hosting_vdsinstance_expired_at_vdsinstance_hosting")],
        )

    def test_initial_migration_contains_only_the_additive_project_server_table(
        self,
    ) -> None:
        self.assertEqual(len(self.migration.operations), 1)
        operation = self.migration.operations[0]

        self.assertIsInstance(operation, migrations.CreateModel)
        self.assertEqual(operation.name, "ProjectServer")
        self.assertEqual(
            [field_name for field_name, _ in operation.fields],
            [
                "id",
                "is_active",
                "created_at",
                "updated_at",
                "ipv4",
                "price",
                "currency",
                "next_payment_date",
                "description",
                "hosting",
            ],
        )

    def test_migration_preserves_field_and_constraint_contracts(self) -> None:
        operation = self.migration.operations[0]
        fields = dict(operation.fields)

        self.assertIsInstance(fields["ipv4"], models.GenericIPAddressField)
        self.assertEqual(fields["ipv4"].protocol, "IPv4")
        self.assertTrue(fields["ipv4"].unique)

        hosting = fields["hosting"]
        self.assertIsInstance(hosting, models.ForeignKey)
        self.assertEqual(hosting.remote_field.model, "vds.hosting")
        self.assertIs(hosting.remote_field.on_delete, models.PROTECT)
        self.assertEqual(hosting.remote_field.related_name, "project_servers")
        self.assertFalse(hosting.null)

        price = fields["price"]
        self.assertEqual(price.max_digits, 10)
        self.assertEqual(price.decimal_places, 2)
        self.assertIn(
            Decimal("0.01"),
            [
                validator.limit_value
                for validator in price.validators
                if isinstance(validator, MinValueValidator)
            ],
        )
        self.assertEqual(fields["currency"].max_length, 4)
        self.assertEqual(
            list(fields["currency"].choices),
            [
                ("USDT", "USDT"),
                ("RUB", "RUB"),
                ("EUR", "EUR"),
                ("USD", "USD"),
            ],
        )
        self.assertEqual(fields["description"].max_length, 255)
        self.assertEqual(
            {constraint.name for constraint in operation.options["constraints"]},
            {"project_server_price_positive", "project_server_currency_valid"},
        )
