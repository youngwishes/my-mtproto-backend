from __future__ import annotations

import io
import sqlite3
import uuid
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.db import IntegrityError, connection
from django.db.models import SET_NULL
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from apps.payments.selectors import get_product_preflight_rows
from apps.users.models import SystemUser
from apps.vds.models import MTPRotoKey


class PaymentsExpandMigrationTest(TransactionTestCase):
    migrate_from = ("payments", "0005_gift_certificates")
    migrate_to = ("payments", "0006_vless_payment_expand")

    def setUp(self) -> None:
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        self.old_apps = self.executor.loader.project_state([self.migrate_from]).apps

    def tearDown(self) -> None:
        old_product = self.old_apps.get_model("payments", "Product")
        old_payment = self.old_apps.get_model("payments", "Payment")
        old_payment.objects.all().delete()
        old_product.objects.all().delete()
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        super().tearDown()

    def _create_product(self, *, is_active: bool = True, title: str = "legacy") -> Any:
        product = self.old_apps.get_model("payments", "Product")
        return product.objects.create(
            is_active=is_active,
            title=title,
            description="legacy description",
            currency="RUB",
            provider_data="{}",
            price="99.00",
            stars_price=80,
        )

    def _create_user(self, *, username: str = "10001") -> Any:
        return SystemUser.objects.create(username=username, password="unused")

    def _create_key(self, *, user: Any) -> Any:
        return MTPRotoKey.objects.create(
            token="test-migration-mtproto-key",
            user=user,
        )

    def _migrate_forward(self) -> Any:
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        return self.executor.loader.project_state([self.migrate_to]).apps

    def test_backfills_only_active_product_code_and_all_legacy_payments(self) -> None:
        active_product = self._create_product(title="active")
        inactive_product = self._create_product(is_active=False, title="inactive")
        user = self._create_user()
        key = self._create_key(user=user)
        old_payment = self.old_apps.get_model("payments", "Payment")
        payment = old_payment.objects.create(
            user_id=user.pk,
            key_id=key.pk,
            charge_id="legacy-charge",
            provider="yukassa",
            kind="subscription",
        )

        new_apps = self._migrate_forward()

        product = new_apps.get_model("payments", "Product")
        migrated_payment = new_apps.get_model("payments", "Payment").objects.get(
            pk=payment.pk
        )
        self.assertEqual(product.objects.get(pk=active_product.pk).code, "mtproto_30d")
        self.assertIsNone(product.objects.get(pk=inactive_product.pk).code)
        self.assertEqual(migrated_payment.product_id, active_product.pk)
        self.assertEqual(migrated_payment.key_id, key.pk)
        key_field = migrated_payment._meta.get_field("key")
        self.assertTrue(key_field.null)
        self.assertTrue(key_field.one_to_one)
        self.assertIs(key_field.remote_field.on_delete, SET_NULL)

    def test_empty_fresh_database_migrates_without_inventing_product(self) -> None:
        new_apps = self._migrate_forward()

        self.assertFalse(new_apps.get_model("payments", "Product").objects.exists())

    def test_preflight_product_inventory_supports_pre_expand_schema(self) -> None:
        product = self._create_product()

        rows = get_product_preflight_rows()

        self.assertEqual(rows, [(product.pk, None, True)])

    def test_preflight_command_runs_against_pre_expand_schema(self) -> None:
        self._create_product()
        with TemporaryDirectory() as temporary_directory:
            backup_path = Path(temporary_directory) / "backup.sqlite3"
            with sqlite3.connect(backup_path) as destination:
                connection.connection.backup(destination)
            stdout = io.StringIO()
            with patch(
                "apps.payments.management.commands.vless_migration_preflight."
                "shutil.disk_usage",
                return_value=SimpleNamespace(free=9_000_000),
            ):
                call_command(
                    "vless_migration_preflight",
                    backup_path=str(backup_path),
                    stdout=stdout,
                )

        self.assertIn("VLESS migration preflight passed", stdout.getvalue())

    def test_multiple_active_products_block_migration(self) -> None:
        self._create_product()
        self._create_product()
        with self.assertRaisesMessage(RuntimeError, "exactly one active Product"):
            self._migrate_forward()

    def test_duplicate_non_empty_payment_identity_blocks_migration(self) -> None:
        self._create_product()
        user = self._create_user()
        old_payment = self.old_apps.get_model("payments", "Payment")
        for kind in ("subscription", "gift_certificate"):
            old_payment.objects.create(
                user_id=user.pk,
                charge_id="duplicate",
                provider="yukassa",
                kind=kind,
            )

        with self.assertRaisesMessage(RuntimeError, "duplicate payment identities"):
            self._migrate_forward()

    def test_preflight_blocks_real_duplicates_on_pre_expand_schema(self) -> None:
        self._create_product()
        user = self._create_user()
        old_payment = self.old_apps.get_model("payments", "Payment")
        for kind in ("subscription", "gift_certificate"):
            old_payment.objects.create(
                user_id=user.pk,
                charge_id="sensitive-duplicate",
                provider="yukassa",
                kind=kind,
            )
        with TemporaryDirectory() as temporary_directory:
            backup_path = Path(temporary_directory) / "backup.sqlite3"
            with sqlite3.connect(backup_path) as destination:
                connection.connection.backup(destination)
            stdout = io.StringIO()
            with (
                patch(
                    "apps.payments.management.commands.vless_migration_preflight."
                    "shutil.disk_usage",
                    return_value=SimpleNamespace(free=9_000_000),
                ),
                self.assertRaisesMessage(
                    CommandError, "duplicate non-empty payment identities"
                ),
            ):
                call_command(
                    "vless_migration_preflight",
                    backup_path=str(backup_path),
                    stdout=stdout,
                )

        self.assertNotIn("sensitive-duplicate", stdout.getvalue())

    def test_general_identity_constraint_ignores_blank_charge_ids(self) -> None:
        self._create_product()
        user = self._create_user()
        new_apps = self._migrate_forward()
        payment = new_apps.get_model("payments", "Payment")
        payment.objects.create(user_id=user.pk, provider="yukassa", charge_id="")
        payment.objects.create(user_id=user.pk, provider="yukassa", charge_id="")
        payment.objects.create(
            user_id=user.pk,
            provider="yukassa",
            charge_id="same",
            kind="subscription",
        )
        payment.objects.create(
            user_id=user.pk,
            provider="stars",
            charge_id="same",
            kind="subscription",
        )

        with self.assertRaises(IntegrityError):
            payment.objects.create(
                user_id=user.pk,
                provider="yukassa",
                charge_id="same",
                kind="gift_certificate",
            )

    def test_product_code_is_unique_only_when_non_empty(self) -> None:
        self._create_product()
        new_apps = self._migrate_forward()
        product = new_apps.get_model("payments", "Product")
        common_fields = {
            "description": "description",
            "currency": "RUB",
            "provider_data": "{}",
            "price": "99.00",
            "stars_price": 80,
        }
        product.objects.create(title="null-code", code=None, **common_fields)
        product.objects.create(title="blank-code-1", code="", **common_fields)
        product.objects.create(title="blank-code-2", code="", **common_fields)

        with self.assertRaises(IntegrityError):
            product.objects.create(
                title="duplicate-code",
                code="mtproto_30d",
                **common_fields,
            )

    def test_legacy_writer_can_insert_payment_without_product_after_expand(self) -> None:
        self._create_product()
        user = self._create_user()
        old_payment = self.old_apps.get_model("payments", "Payment")
        new_apps = self._migrate_forward()

        legacy_row = old_payment.objects.create(
            user_id=user.pk,
            charge_id="rollback-window",
            provider="stars",
            kind="subscription",
        )

        migrated = new_apps.get_model("payments", "Payment").objects.get(
            pk=legacy_row.pk
        )
        self.assertIsNone(migrated.product_id)
        self.assertIsNone(migrated.key_id)


class PaymentReceiptAppliedAtMigrationTest(TransactionTestCase):
    migrate_from = ("payments", "0007_paymentintent_paymentreceipt")
    migrate_to = ("payments", "0009_receipt_ready_at")

    def setUp(self) -> None:
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        self.old_apps = self.executor.loader.project_state([self.migrate_from]).apps

    def tearDown(self) -> None:
        MigrationExecutor(connection).migrate(
            [self.migrate_to, ("vpn", "0004_access_first_ready_at")]
        )
        super().tearDown()

    def test_forward_backfills_terminal_timestamp_and_reverse_preserves_receipt(
        self,
    ) -> None:
        user = SystemUser.objects.create(username="receipt-migration-user")
        Product = self.old_apps.get_model("payments", "Product")
        PaymentIntent = self.old_apps.get_model("payments", "PaymentIntent")
        Payment = self.old_apps.get_model("payments", "Payment")
        PaymentReceipt = self.old_apps.get_model("payments", "PaymentReceipt")
        product = Product.objects.create(
            code="vless_30d",
            title="VLESS",
            description="VLESS",
            currency="RUB",
            provider_data="{}",
            price="99.00",
            stars_price=80,
        )
        intent = PaymentIntent.objects.create(
            user_id=user.pk,
            product_id=product.pk,
            invoice_payload="a" * 64,
            currency="RUB",
            amount=9900,
            provider="yukassa",
            expires_at=timezone.now() + timedelta(minutes=15),
            status="paid",
        )
        payment = Payment.objects.create(
            user_id=user.pk,
            product_id=product.pk,
            charge_id="receipt-migration-charge",
            provider="yukassa",
            kind="subscription",
        )
        receipt = PaymentReceipt.objects.create(
            intent_id=intent.pk,
            user_id=user.pk,
            product_id=product.pk,
            provider="yukassa",
            charge_id=payment.charge_id,
            currency="RUB",
            amount=9900,
            status="applied",
            payment_id=payment.pk,
        )
        historical_vpn_apps = self.executor.loader.project_state(
            [("vpn", "0004_access_first_ready_at")]
        ).apps
        access_model = historical_vpn_apps.get_model("vpn", "VPNAccess")
        purchase_model = historical_vpn_apps.get_model("vpn", "VPNPurchase")
        credential = uuid.uuid4()
        access = access_model.objects.create(
            user_id=user.pk,
            subscription_token="y" * 43,
            desired_uuid=credential,
            desired_revision=1,
            published_uuid=credential,
            published_revision=1,
            expired_at=timezone.now() + timedelta(days=30),
            state="ready",
            state_revision=1,
            first_ready_at=timezone.now(),
        )
        purchase_model.objects.create(
            payment_id=payment.pk,
            access_id=access.pk,
            period_days=30,
            expired_at_after=access.expired_at,
        )

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        new_apps = executor.loader.project_state([self.migrate_to]).apps
        migrated = new_apps.get_model("payments", "PaymentReceipt").objects.get(
            pk=receipt.pk
        )
        self.assertEqual(migrated.applied_at, migrated.updated_at)
        self.assertIsNotNone(migrated.ready_at)
        self.assertGreaterEqual(migrated.ready_at, migrated.applied_at)

        now = timezone.now()
        post_expand_user = SystemUser.objects.create(
            username="post-expand-receipt-migration-user"
        )
        post_expand_intent = PaymentIntent.objects.create(
            user_id=post_expand_user.pk,
            product_id=product.pk,
            invoice_payload="b" * 64,
            currency="RUB",
            amount=9900,
            provider="yukassa",
            expires_at=now + timedelta(minutes=15),
            status="paid",
        )
        post_expand_payment = Payment.objects.create(
            user_id=post_expand_user.pk,
            product_id=product.pk,
            charge_id="post-expand-old-writer",
            provider="yukassa",
            kind="subscription",
        )
        post_expand_receipt = PaymentReceipt.objects.create(
            intent_id=post_expand_intent.pk,
            user_id=post_expand_user.pk,
            product_id=product.pk,
            provider="yukassa",
            charge_id=post_expand_payment.charge_id,
            currency="RUB",
            amount=9900,
            status="applied",
            payment_id=post_expand_payment.pk,
        )
        PaymentReceipt.objects.filter(pk=post_expand_receipt.pk).update(
            accepted_at=now - timedelta(minutes=10),
            updated_at=now - timedelta(minutes=7),
        )
        historical_vpn_apps = executor.loader.project_state(
            [("vpn", "0003_observability_onsets")]
        ).apps
        old_access_model = historical_vpn_apps.get_model("vpn", "VPNAccess")
        old_purchase_model = historical_vpn_apps.get_model("vpn", "VPNPurchase")
        credential = uuid.uuid4()
        post_expand_access = old_access_model.objects.create(
            user_id=post_expand_user.pk,
            subscription_token="z" * 43,
            desired_uuid=credential,
            desired_revision=1,
            published_uuid=credential,
            published_revision=1,
            expired_at=now + timedelta(days=30),
            state="ready",
            state_revision=1,
        )
        old_access_model.objects.filter(pk=post_expand_access.pk).update(
            updated_at=now - timedelta(minutes=2)
        )
        old_purchase_model.objects.create(
            payment_id=post_expand_payment.pk,
            access_id=post_expand_access.pk,
            period_days=30,
            expired_at_after=now + timedelta(days=30),
        )

        current_receipt = new_apps.get_model("payments", "PaymentReceipt").objects.get(
            pk=post_expand_receipt.pk
        )
        current_access = MigrationExecutor(connection).loader.project_state(
            [("vpn", "0004_access_first_ready_at")]
        ).apps.get_model("vpn", "VPNAccess").objects.get(pk=post_expand_access.pk)
        self.assertIsNone(current_receipt.applied_at)
        self.assertIsNone(current_receipt.ready_at)
        self.assertIsNone(current_access.first_ready_at)
        from apps.vpn.observability import get_vpn_observation

        values = {
            metric.name: metric.value
            for metric in get_vpn_observation(at=now).metrics
        }
        self.assertEqual(values["vpn_receipts_applied_current"], 2)
        self.assertEqual(values["vpn_receipt_apply_latency_seconds"], 180)
        self.assertEqual(values["vpn_readiness_latency_seconds"], 300)

        reverse = MigrationExecutor(connection)
        reverse.migrate(
            [self.migrate_from, ("vpn", "0003_observability_onsets")]
        )
        reversed_apps = reverse.loader.project_state([self.migrate_from]).apps
        self.assertEqual(
            reversed_apps.get_model("payments", "PaymentReceipt")
            .objects.filter(pk__in=(receipt.pk, post_expand_receipt.pk))
            .count(),
            2,
        )
