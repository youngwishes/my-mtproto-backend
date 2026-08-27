from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class TestCryptoPaymentMigration(TransactionTestCase):
    migrate_from = ("payments", "0006_product_code_vpn_payment")
    migrate_to = ("payments", "0007_crypto_payment_intent")
    users_target = ("users", "0018_systemuser_apple_balance")

    def setUp(self) -> None:
        super().setUp()
        self.executor = MigrationExecutor(connection)
        before_targets = [self.migrate_from, self.users_target]
        self.executor.migrate(before_targets)
        old_apps = self.executor.loader.project_state(before_targets).apps
        user = old_apps.get_model("users", "SystemUser").objects.create(
            username="legacy-user",
        )
        product = old_apps.get_model("payments", "Product").objects.create(
            code="mtproto_30d",
            title="Legacy product",
            description="Legacy product",
            provider_data="{}",
            price=Decimal("9900.00"),
            stars_price=99,
        )
        payment = old_apps.get_model("payments", "Payment").objects.create(
            user_id=user.pk,
            key=None,
            provider="stars",
            charge_id="legacy-charge",
            kind="gift_certificate",
        )
        gift = old_apps.get_model("payments", "GiftCertificate").objects.create(
            code="KEY-T001-ABCD",
            buyer_id=user.pk,
            payment_id=payment.pk,
            expires_at=timezone.now() + timedelta(days=30),
        )
        self.legacy_ids = (product.pk, payment.pk, gift.pk)

        self.executor = MigrationExecutor(connection)
        after_targets = [self.migrate_to, self.users_target]
        self.executor.migrate(after_targets)
        self.apps = self.executor.loader.project_state(after_targets).apps

    def tearDown(self) -> None:
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_forward_preserves_legacy_products_payments_and_gifts(self) -> None:
        product_id, payment_id, gift_id = self.legacy_ids
        product = self.apps.get_model("payments", "Product")
        payment = self.apps.get_model("payments", "Payment")
        gift = self.apps.get_model("payments", "GiftCertificate")

        self.assertEqual(product.objects.get(pk=product_id).code, "mtproto_30d")
        self.assertEqual(payment.objects.get(pk=payment_id).charge_id, "legacy-charge")
        self.assertEqual(gift.objects.get(pk=gift_id).code, "KEY-T001-ABCD")

    def test_schema_contains_crypto_only_partial_constraints(self) -> None:
        constraints = connection.introspection.get_constraints(
            connection.cursor(), "payments_payment"
        )
        self.assertIn("uniq_crypto_payment_identity", constraints)
        self.assertIn(
            "uniq_active_crypto_intent_per_user_kind",
            connection.introspection.get_constraints(
                connection.cursor(), "payments_cryptopaymentintent"),
        )
