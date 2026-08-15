from __future__ import annotations

from django.db import connection, models
from django.db.migrations import AddField
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.test import SimpleTestCase, TransactionTestCase

from apps.users.models import SystemUser


class TestVPNMigrationPackage(SimpleTestCase):
    def test_initial_migration_is_discoverable(self) -> None:
        loader = MigrationLoader(None, load=False)
        loader.load_disk()

        self.assertIn(("vpn", "0001_initial"), loader.disk_migrations)

    def test_reissue_timestamp_migration_is_one_additive_field(self) -> None:
        """Catches a migration that is missing, rewrites history, or changes more than the timestamp."""
        loader = MigrationLoader(None, load=False)
        loader.load_disk()

        migration = loader.disk_migrations[("vpn", "0002_vpnsubscription_last_reissued_at")]

        self.assertEqual(migration.dependencies, [("vpn", "0001_initial")])
        self.assertEqual(len(migration.operations), 1)
        operation = migration.operations[0]
        self.assertIsInstance(operation, AddField)
        self.assertEqual(operation.model_name, "vpnsubscription")
        self.assertEqual(operation.name, "last_reissued_at")
        self.assertTrue(operation.field.null)
        self.assertTrue(operation.field.blank)
        self.assertIs(operation.field.default, models.NOT_PROVIDED)


class TestVPNReissueMigrationCompatibility(TransactionTestCase):
    def test_existing_subscription_keeps_state_and_gets_null_reissue_timestamp(self) -> None:
        """Catches an additive migration that alters existing VPN credentials or lifecycle state."""
        executor = MigrationExecutor(connection)
        migrate_from = [("vpn", "0001_initial")]
        migrate_to = [("vpn", "0002_vpnsubscription_last_reissued_at")]
        executor.migrate(migrate_from)
        old_apps = executor.loader.project_state(migrate_from).apps
        old_subscription_model = old_apps.get_model("vpn", "VPNSubscription")
        user = SystemUser.objects.create(username="migration-user")
        old_subscription = old_subscription_model.objects.create(
            user_id=user.pk,
            token="old-token",
            vless_uuid="11111111-1111-1111-1111-111111111111",
            hysteria_secret="old-hysteria-secret",
            expired_at="2026-09-01T12:00:00Z",
            is_active=False,
        )

        executor = MigrationExecutor(connection)
        executor.migrate(migrate_to)
        new_apps = executor.loader.project_state(migrate_to).apps
        new_subscription_model = new_apps.get_model("vpn", "VPNSubscription")
        migrated_subscription = new_subscription_model.objects.get(pk=old_subscription.pk)

        self.assertEqual(migrated_subscription.token, "old-token")
        self.assertEqual(
            str(migrated_subscription.vless_uuid),
            "11111111-1111-1111-1111-111111111111",
        )
        self.assertEqual(migrated_subscription.hysteria_secret, "old-hysteria-secret")
        self.assertEqual(str(migrated_subscription.expired_at), "2026-09-01 12:00:00+00:00")
        self.assertFalse(migrated_subscription.is_active)
        self.assertIsNone(migrated_subscription.last_reissued_at)
