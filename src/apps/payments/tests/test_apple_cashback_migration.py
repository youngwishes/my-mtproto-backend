from __future__ import annotations

from datetime import UTC, datetime

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class TestAppleCashbackBackfillMigration(TransactionTestCase):
    migrate_from = ("payments", "0013_apple_cashback_schema")
    migrate_to = ("payments", "0014_backfill_apple_cashback_purchases")

    def setUp(self) -> None:
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        old_apps = self.executor.loader.project_state([self.migrate_from]).apps

        user = old_apps.get_model("users", "SystemUser")
        payment = old_apps.get_model("payments", "Payment")
        gift_certificate = old_apps.get_model("payments", "GiftCertificate")
        self.alice = user.objects.create(username="alice")
        self.bob = user.objects.create(username="bob")
        self.recipient = user.objects.create(username="recipient")

        first_subscription = payment.objects.create(
            user_id=self.alice.pk,
            provider="stars",
            charge_id="same-charge",
            kind="subscription",
        )
        duplicate_subscription = payment.objects.create(
            user_id=self.bob.pk,
            provider="stars",
            charge_id="same-charge",
            kind="subscription",
        )
        blank_subscription = payment.objects.create(
            user_id=self.alice.pk,
            provider="stars",
            charge_id="",
            kind="subscription",
        )
        gift_payment = payment.objects.create(
            user_id=self.alice.pk,
            provider="stars",
            charge_id="gift-charge",
            kind="gift_certificate",
        )
        gift_certificate.objects.create(
            code="KEY-T001-ABCD",
            buyer_id=self.alice.pk,
            payment_id=gift_payment.pk,
            expires_at=timezone.now(),
            activated_by_id=self.recipient.pk,
            status="activated",
        )
        bob_payment = payment.objects.create(
            user_id=self.bob.pk,
            provider="crypto_pay",
            charge_id="bob-charge",
            kind="gift_certificate",
        )
        vpn_payment = payment.objects.create(
            user_id=self.alice.pk,
            provider="stars",
            charge_id="vpn-charge",
            kind="vpn_subscription",
        )
        payment.objects.filter(pk=first_subscription.pk).update(
            created_at=datetime(2026, 1, 1, tzinfo=UTC)
        )
        payment.objects.filter(pk=duplicate_subscription.pk).update(
            created_at=datetime(2026, 1, 2, tzinfo=UTC)
        )
        payment.objects.filter(pk=blank_subscription.pk).update(
            created_at=datetime(2026, 1, 3, tzinfo=UTC)
        )
        payment.objects.filter(pk=gift_payment.pk).update(
            created_at=datetime(2026, 1, 4, tzinfo=UTC)
        )
        payment.objects.filter(pk=bob_payment.pk).update(
            created_at=datetime(2026, 1, 5, tzinfo=UTC)
        )
        payment.objects.filter(pk=vpn_payment.pk).update(
            created_at=datetime(2026, 1, 6, tzinfo=UTC)
        )
        self.first_subscription_id = first_subscription.pk
        self.blank_subscription_id = blank_subscription.pk
        self.gift_payment_id = gift_payment.pk
        self.bob_payment_id = bob_payment.pk

        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        self.apps = self.executor.loader.project_state([self.migrate_to]).apps

    def tearDown(self) -> None:
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_forward_creates_only_deduplicated_eligible_history_with_zero_apples(self) -> None:
        purchase = self.apps.get_model("payments", "AppleCashbackPurchase")
        user = self.apps.get_model("users", "SystemUser")

        self.assertEqual(
            list(
                purchase.objects.order_by("eligible_purchase_count_after", "pk").values_list(
                    "payment_id",
                    "identity_key",
                    "payment__user_id",
                    "rate_percent",
                    "apples_earned",
                    "balance_after",
                    "eligible_purchase_count_after",
                    "result_expired_at",
                )
            ),
            [
                (
                    self.first_subscription_id,
                    "stars:same-charge:subscription",
                    self.alice.pk,
                    None,
                    0,
                    0,
                    1,
                    None,
                ),
                (
                    self.bob_payment_id,
                    "crypto_pay:bob-charge:gift_certificate",
                    self.bob.pk,
                    None,
                    0,
                    0,
                    1,
                    None,
                ),
                (
                    self.blank_subscription_id,
                    f"legacy:{self.blank_subscription_id}",
                    self.alice.pk,
                    None,
                    0,
                    0,
                    2,
                    None,
                ),
                (
                    self.gift_payment_id,
                    "stars:gift-charge:gift_certificate",
                    self.alice.pk,
                    None,
                    0,
                    0,
                    3,
                    None,
                ),
            ],
        )
        self.assertEqual(
            list(user.objects.order_by("username").values_list("username", "apple_balance")),
            [("alice", 0), ("bob", 0), ("recipient", 0)],
        )

    def test_reverse_deletes_only_historical_rows_and_keeps_the_additive_schema(self) -> None:
        payment = self.apps.get_model("payments", "Payment")
        purchase = self.apps.get_model("payments", "AppleCashbackPurchase")
        current_payment = payment.objects.create(
            user_id=self.alice.pk,
            provider="stars",
            charge_id="post-launch",
            kind="subscription",
        )
        purchase.objects.create(
            payment_id=current_payment.pk,
            identity_key="stars:post-launch:subscription",
            rate_percent=5,
            apples_earned=5,
            balance_after=5,
            eligible_purchase_count_after=4,
        )

        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        apps_after_reverse = self.executor.loader.project_state([self.migrate_from]).apps
        purchase_after_reverse = apps_after_reverse.get_model(
            "payments", "AppleCashbackPurchase"
        )
        user_after_reverse = apps_after_reverse.get_model("users", "SystemUser")

        self.assertEqual(
            list(purchase_after_reverse.objects.values_list("identity_key", flat=True)),
            ["stars:post-launch:subscription"],
        )
        self.assertTrue(
            hasattr(user_after_reverse, "apple_balance"),
        )
        apps_after_reverse.get_model("payments", "Payment").objects.filter(
            pk=current_payment.pk
        ).delete()
