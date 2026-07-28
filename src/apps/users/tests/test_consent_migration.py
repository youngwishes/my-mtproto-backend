from __future__ import annotations

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from apps.users.models import SystemUser


class TestLegalConsentMigration(TestCase):
    def test_new_user_defaults_to_not_accepted(self) -> None:
        user = SystemUser.objects.create(username="100")

        self.assertFalse(user.legal_terms_accepted)


class TestLegalConsentMigrationTransition(TransactionTestCase):
    migrate_from = ("users", "0016_normalize_none_usernames")
    migrate_to = ("users", "0017_systemuser_legal_terms_accepted")

    def setUp(self) -> None:
        executor = MigrationExecutor(connection)
        self.leaf_nodes = executor.loader.graph.leaf_nodes()
        self.addCleanup(self._restore_leaf_migrations)

    def _restore_leaf_migrations(self) -> None:
        MigrationExecutor(connection).migrate(self.leaf_nodes)

    def test_backfill_and_old_code_insert_after_schema_migration(self) -> None:
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        OldSystemUser = old_apps.get_model("users", "SystemUser")
        existing = OldSystemUser.objects.create(
            username="101",
            telegram_username="first",
            invited_from_username="900",
            first_month_free_used=True,
            referral_activated=True,
        )

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        new_apps = executor.loader.project_state([self.migrate_to]).apps
        NewSystemUser = new_apps.get_model("users", "SystemUser")

        migrated = NewSystemUser.objects.get(pk=existing.pk)
        self.assertEqual(NewSystemUser.objects.count(), 1)
        self.assertTrue(migrated.legal_terms_accepted)
        self.assertEqual(
            (
                migrated.username,
                migrated.telegram_username,
                migrated.invited_from_username,
                migrated.first_month_free_used,
                migrated.referral_activated,
            ),
            ("101", "first", "900", True, True),
        )

        legacy_insert = OldSystemUser.objects.create(
            username="102",
            telegram_username="legacy",
        )

        inserted = NewSystemUser.objects.get(pk=legacy_insert.pk)
        self.assertEqual(NewSystemUser.objects.count(), 2)
        self.assertFalse(inserted.legal_terms_accepted)
