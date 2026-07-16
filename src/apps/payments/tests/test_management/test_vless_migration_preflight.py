from __future__ import annotations

import io
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.db import connection
from django.test import TransactionTestCase

from apps.payments.enums import PaymentKindEnum, PaymentProviderEnum, ProductCodeEnum
from apps.payments.models import Payment, Product
from apps.payments.tests.factories import (
    GiftCertificateFactory,
    PaymentFactory,
    ProductFactory,
)


class VlessMigrationPreflightTest(TransactionTestCase):
    def setUp(self) -> None:
        self.product = ProductFactory(
            code=ProductCodeEnum.MTPROTO_30D,
            title="commercial secret title",
        )
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.backup_path = Path(self.temporary_directory.name) / "backup.sqlite3"
        self._write_valid_backup()

    def _write_valid_backup(self) -> None:
        with sqlite3.connect(self.backup_path) as destination:
            connection.connection.backup(destination)

    def _run(self) -> str:
        stdout = io.StringIO()
        with patch(
            "apps.payments.management.commands.vless_migration_preflight.shutil.disk_usage",
            return_value=SimpleNamespace(free=9_000_000),
        ):
            call_command(
                "vless_migration_preflight",
                backup_path=str(self.backup_path),
                stdout=stdout,
            )
        return stdout.getvalue()

    def _assert_blocked(self, *, expected: str) -> str:
        stdout = io.StringIO()
        with (
            patch(
                "apps.payments.management.commands.vless_migration_preflight.shutil.disk_usage",
                return_value=SimpleNamespace(free=9_000_000),
            ),
            self.assertRaisesMessage(CommandError, expected),
        ):
            call_command(
                "vless_migration_preflight",
                backup_path=str(self.backup_path),
                stdout=stdout,
            )
        return stdout.getvalue()

    def test_valid_production_like_data_passes_without_mutation(self) -> None:
        blank_payment = PaymentFactory(charge_id="")
        gift_payment = PaymentFactory(
            charge_id="gift-identity",
            provider=PaymentProviderEnum.STARS,
            kind=PaymentKindEnum.GIFT_CERTIFICATE,
        )
        before = list(
            Payment.objects.order_by("pk").values_list(
                "pk", "user_id", "key_id", "charge_id", "provider", "kind"
            )
        )

        output = self._run()

        self.assertIn("VLESS migration preflight passed", output)
        self.assertEqual(
            list(
                Payment.objects.order_by("pk").values_list(
                    "pk", "user_id", "key_id", "charge_id", "provider", "kind"
                )
            ),
            before,
        )
        self.assertTrue(Product.objects.filter(pk=self.product.pk, is_active=True).exists())
        self.assertTrue(Payment.objects.filter(pk=blank_payment.pk).exists())
        self.assertTrue(Payment.objects.filter(pk=gift_payment.pk).exists())

    def test_zero_active_products_is_blocked(self) -> None:
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])

        output = self._assert_blocked(expected="expected exactly one active Product")

        self.assertIn(f"pk={self.product.pk}", output)
        self.assertIn("status=inactive", output)
        self.assertNotIn(self.product.title, output)

    def test_multiple_active_products_are_blocked_with_safe_output(self) -> None:
        other = ProductFactory(
            code=ProductCodeEnum.VLESS_30D,
            title="another commercial title",
        )

        output = self._assert_blocked(expected="expected exactly one active Product")

        self.assertIn(f"pk={self.product.pk}", output)
        self.assertIn(f"pk={other.pk}", output)
        self.assertIn("code=vless_30d", output)
        self.assertNotIn(self.product.title, output)
        self.assertNotIn(other.title, output)
        self.assertNotIn(str(self.product.price), output)

    def test_duplicate_non_empty_payment_identity_is_blocked(self) -> None:
        with patch(
            "apps.payments.management.commands.vless_migration_preflight."
            "get_duplicate_non_empty_payment_identity_count",
            return_value=1,
        ):
            output = self._assert_blocked(
                expected="duplicate non-empty payment identities"
            )

        self.assertNotIn("provider-secret-identity", output)
        self.assertNotIn(PaymentProviderEnum.YUKASSA, output)

    def test_orphan_relation_is_blocked(self) -> None:
        payment = PaymentFactory()
        with connection.constraint_checks_disabled():
            Payment.objects.filter(pk=payment.pk).update(user_id=999_999_999)

        output = self._assert_blocked(expected="orphan relations")

        self.assertIn("payments_payment", output)
        self.assertIn(f"pk={payment.pk}", output)
        self.assertNotIn(payment.charge_id, output)

    def test_orphan_gift_relation_is_blocked(self) -> None:
        gift = GiftCertificateFactory()
        with connection.constraint_checks_disabled():
            type(gift).objects.filter(pk=gift.pk).update(payment_id=999_999_999)

        output = self._assert_blocked(expected="orphan relations")

        self.assertIn("payments_giftcertificate", output)
        self.assertIn(f"pk={gift.pk}", output)
        self.assertNotIn(gift.code, output)

    def test_missing_or_invalid_backup_is_blocked(self) -> None:
        self.backup_path.unlink()

        self._assert_blocked(expected="SQLite backup is not prepared")

        self.backup_path.write_text("not a sqlite backup")
        self._assert_blocked(expected="SQLite backup is not prepared")

        self.backup_path.unlink()
        with sqlite3.connect(self.backup_path) as unrelated_database:
            unrelated_database.execute("CREATE TABLE unrelated (id INTEGER)")
        self._assert_blocked(expected="SQLite backup is not prepared")

    def test_live_database_path_alias_is_rejected_before_sqlite_open(self) -> None:
        live_database_path = Path(self.temporary_directory.name) / "live.sqlite3"
        live_database_path.write_bytes(b"live database must not be opened as backup")
        alias_directory = Path(self.temporary_directory.name) / "alias"
        alias_directory.mkdir()
        normalized_alias = alias_directory / ".." / live_database_path.name
        stdout = io.StringIO()

        with (
            patch.dict(connection.settings_dict, {"NAME": str(live_database_path)}),
            patch(
                "apps.payments.management.commands.vless_migration_preflight."
                "sqlite3.connect"
            ) as sqlite_connect,
            patch(
                "apps.payments.management.commands.vless_migration_preflight."
                "shutil.disk_usage",
                return_value=SimpleNamespace(free=9_000_000),
            ),
            self.assertRaisesMessage(CommandError, "SQLite backup is not prepared"),
        ):
            call_command(
                "vless_migration_preflight",
                backup_path=str(normalized_alias),
                stdout=stdout,
            )

        sqlite_connect.assert_not_called()
        self.assertEqual(
            live_database_path.read_bytes(),
            b"live database must not be opened as backup",
        )
        self.assertNotIn(str(live_database_path), stdout.getvalue())
        self.assertNotIn(str(normalized_alias), stdout.getvalue())

    def test_backup_with_orphan_foreign_key_is_rejected_without_mutation(self) -> None:
        orphan_backup = Path(self.temporary_directory.name) / "orphan.sqlite3"
        with sqlite3.connect(orphan_backup) as database:
            database.executescript(
                """
                PRAGMA foreign_keys = OFF;
                CREATE TABLE django_migrations (id INTEGER PRIMARY KEY);
                CREATE TABLE payments_product (id INTEGER PRIMARY KEY);
                CREATE TABLE users_systemuser (id INTEGER PRIMARY KEY);
                CREATE TABLE payments_payment (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users_systemuser(id),
                    charge_id TEXT NOT NULL
                );
                CREATE TABLE payments_giftcertificate (
                    id INTEGER PRIMARY KEY,
                    payment_id INTEGER NOT NULL REFERENCES payments_payment(id)
                );
                INSERT INTO payments_payment (id, user_id, charge_id)
                    VALUES (1, 999999, 'sensitive-provider-value');
                """
            )
            self.assertEqual(
                database.execute("PRAGMA integrity_check").fetchone(),
                ("ok",),
            )
        before = orphan_backup.read_bytes()
        stdout = io.StringIO()

        with (
            patch(
                "apps.payments.management.commands.vless_migration_preflight."
                "shutil.disk_usage",
                return_value=SimpleNamespace(free=9_000_000),
            ),
            self.assertRaisesMessage(CommandError, "SQLite backup is not prepared"),
        ):
            call_command(
                "vless_migration_preflight",
                backup_path=str(orphan_backup),
                stdout=stdout,
            )

        self.assertEqual(orphan_backup.read_bytes(), before)
        self.assertNotIn(str(orphan_backup), stdout.getvalue())
        self.assertNotIn("sensitive-provider-value", stdout.getvalue())
        self.assertNotIn("999999", stdout.getvalue())

    def test_insufficient_free_space_is_blocked(self) -> None:
        stdout = io.StringIO()
        with (
            patch(
                "apps.payments.management.commands.vless_migration_preflight.shutil.disk_usage",
                return_value=SimpleNamespace(free=1),
            ),
            self.assertRaisesMessage(CommandError, "insufficient free space"),
        ):
            call_command(
                "vless_migration_preflight",
                backup_path=str(self.backup_path),
                stdout=stdout,
            )

        self.assertNotIn(str(self.backup_path), stdout.getvalue())
