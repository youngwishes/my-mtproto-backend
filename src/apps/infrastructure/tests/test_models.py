from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import IntegrityError, models, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from apps.core import BaseDjangoModel
from apps.infrastructure.enums import ProjectServerCurrency
from apps.infrastructure.models import ProjectServer
from apps.infrastructure.tests.factories import ProjectServerFactory
from apps.vds.models import Hosting
from apps.vds.tests.factories import HostingFactory


class ProjectServerCurrencyTest(TestCase):
    def test_currency_exposes_only_the_approved_codes_and_labels(self) -> None:
        self.assertEqual(
            list(ProjectServerCurrency.__members__),
            ["USDT", "RUB", "EUR", "USD"],
        )
        self.assertEqual(
            list(ProjectServerCurrency.choices),
            [
                ("USDT", "USDT"),
                ("RUB", "RUB"),
                ("EUR", "EUR"),
                ("USD", "USD"),
            ],
        )


class ProjectServerModelMetadataTest(TestCase):
    def test_model_has_only_approved_and_inherited_fields(self) -> None:
        self.assertTrue(issubclass(ProjectServer, BaseDjangoModel))
        self.assertEqual(
            [field.name for field in ProjectServer._meta.fields],
            [
                "id",
                "is_active",
                "created_at",
                "updated_at",
                "ipv4",
                "hosting",
                "price",
                "currency",
                "next_payment_date",
                "description",
            ],
        )

    def test_fields_match_the_approved_persistence_contract(self) -> None:
        ipv4 = ProjectServer._meta.get_field("ipv4")
        hosting = ProjectServer._meta.get_field("hosting")
        price = ProjectServer._meta.get_field("price")
        currency = ProjectServer._meta.get_field("currency")
        next_payment_date = ProjectServer._meta.get_field("next_payment_date")
        description = ProjectServer._meta.get_field("description")

        self.assertIsInstance(ipv4, models.GenericIPAddressField)
        self.assertEqual(ipv4.protocol, "IPv4")
        self.assertTrue(ipv4.unique)

        self.assertIsInstance(hosting, models.ForeignKey)
        self.assertIs(hosting.remote_field.model, Hosting)
        self.assertIs(hosting.remote_field.on_delete, models.PROTECT)
        self.assertEqual(hosting.remote_field.related_name, "project_servers")
        self.assertFalse(hosting.null)
        self.assertFalse(hosting.blank)

        self.assertIsInstance(price, models.DecimalField)
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

        self.assertIsInstance(currency, models.CharField)
        self.assertEqual(currency.max_length, 4)
        self.assertEqual(list(currency.choices), list(ProjectServerCurrency.choices))
        self.assertIsInstance(next_payment_date, models.DateField)
        self.assertIsInstance(description, models.CharField)
        self.assertEqual(description.max_length, 255)

    def test_model_declares_the_approved_database_constraints(self) -> None:
        self.assertEqual(
            {constraint.name for constraint in ProjectServer._meta.constraints},
            {"project_server_price_positive", "project_server_currency_valid"},
        )


class ProjectServerValidationTest(TestCase):
    def setUp(self) -> None:
        self.hosting = HostingFactory()

    def build_server(self, **overrides: object) -> ProjectServer:
        attributes: dict[str, object] = {"hosting": self.hosting}
        attributes.update(overrides)
        return ProjectServerFactory.build(**attributes)

    def test_full_clean_rejects_malformed_and_ipv6_addresses(self) -> None:
        for ipv4 in ("not-an-ip", "2001:db8::1"):
            with self.subTest(ipv4=ipv4):
                server = self.build_server(ipv4=ipv4)

                with self.assertRaises(ValidationError) as error:
                    server.full_clean()

                self.assertIn("ipv4", error.exception.message_dict)

    def test_full_clean_rejects_each_missing_required_value(self) -> None:
        for field_name in (
            "ipv4",
            "hosting",
            "price",
            "currency",
            "next_payment_date",
            "description",
        ):
            with self.subTest(field_name=field_name):
                server = self.build_server(**{field_name: None})

                with self.assertRaises(ValidationError) as error:
                    server.full_clean()

                self.assertIn(field_name, error.exception.message_dict)

    def test_full_clean_rejects_duplicate_ipv4(self) -> None:
        existing = ProjectServerFactory(ipv4="192.0.2.10")
        duplicate = self.build_server(ipv4=existing.ipv4)

        with self.assertRaises(ValidationError) as error:
            duplicate.full_clean()

        self.assertIn("ipv4", error.exception.message_dict)

    def test_full_clean_rejects_non_positive_price(self) -> None:
        for price in (Decimal("0.00"), Decimal("-0.01")):
            with self.subTest(price=price):
                server = self.build_server(price=price)

                with self.assertRaises(ValidationError) as error:
                    server.full_clean()

                self.assertIn("price", error.exception.message_dict)

    def test_full_clean_rejects_unsupported_currency(self) -> None:
        server = self.build_server(currency="GBP")

        with self.assertRaises(ValidationError) as error:
            server.full_clean()

        self.assertIn("currency", error.exception.message_dict)


class ProjectServerDatabaseConstraintTest(TestCase):
    def test_database_rejects_duplicate_ipv4(self) -> None:
        ProjectServerFactory(ipv4="192.0.2.20")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProjectServerFactory(ipv4="192.0.2.20")

    def test_database_rejects_non_positive_price(self) -> None:
        for price in (Decimal("0.00"), Decimal("-0.01")):
            with self.subTest(price=price):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        ProjectServerFactory(price=price)

    def test_database_rejects_unsupported_currency(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProjectServerFactory(currency="GBP")

    def test_referenced_hosting_is_protected_from_deletion(self) -> None:
        server = ProjectServerFactory()

        with self.assertRaises(ProtectedError):
            server.hosting.delete()

        self.assertTrue(Hosting.objects.filter(pk=server.hosting_id).exists())


class ProjectServerBehaviorTest(TestCase):
    def test_active_manager_returns_only_active_servers(self) -> None:
        active = ProjectServerFactory(is_active=True)
        ProjectServerFactory(is_active=False)

        self.assertEqual(list(ProjectServer.objects.active()), [active])

    def test_string_representation_is_ipv4(self) -> None:
        server = ProjectServerFactory(ipv4="192.0.2.30")

        self.assertEqual(str(server), "192.0.2.30")
