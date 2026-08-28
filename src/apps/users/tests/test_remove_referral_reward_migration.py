from __future__ import annotations

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class TestRemoveReferralRewardMigration(TransactionTestCase):
    migrate_from = ("users", "0018_systemuser_apple_balance")
    migrate_to = ("users", "0019_remove_systemuser_referral_link_activated_count")

    def setUp(self) -> None:
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])

        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        self.apps = self.executor.loader.project_state([self.migrate_to]).apps

    def tearDown(self) -> None:
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_keeps_legacy_column_for_application_rollback(self) -> None:
        with connection.cursor() as cursor:
            columns = {
                column.name
                for column in connection.introspection.get_table_description(
                    cursor,
                    "users_systemuser",
                )
            }

        self.assertIn("referral_link_activated_count", columns)
        system_user = self.apps.get_model("users", "SystemUser")
        self.assertNotIn(
            "referral_link_activated_count",
            {field.name for field in system_user._meta.get_fields()},
        )
        created_user = system_user.objects.create(username="new-referral-user")
        self.assertEqual(created_user.username, "new-referral-user")
