from __future__ import annotations

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class TestSorryServerErrorSupportMigration(TransactionTestCase):
    migrate_from = ("notifications", "0011_seed_crypto_purchase_templates")
    migrate_to = ("notifications", "0012_update_sorry_server_error_support")
    sorry_text = (
        "Server error fixture body.\n\n"
        "📩 <b>Поддержка:</b> @mtproto_keys\n\n"
        "Server error fixture footer."
    )
    invite_text = (
        "News invitation fixture body.\n\n"
        "Подпишитесь на новостной канал: @mtproto_keys"
    )

    @staticmethod
    def _snapshot(template) -> dict[str, object]:
        return {
            field.name: getattr(template, field.name)
            for field in template._meta.concrete_fields
        }

    def setUp(self) -> None:
        super().setUp()
        self.addCleanup(self._restore_leaf_state)
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        old_apps = self.executor.loader.project_state([self.migrate_from]).apps
        template = old_apps.get_model("notifications", "NotificationTemplate")
        template.objects.update_or_create(
            slug="sorry_server_error",
            defaults={
                "is_active": True,
                "title": "Server error fixture title",
                "text": self.sorry_text,
                "button_text": "Server error fixture button",
                "button_url": "https://example.com/support-fixture",
                "button_callback_data": "server_error_fixture",
                "include_payment_buttons": True,
            },
        )
        template.objects.update_or_create(
            slug="invite_to_channel",
            defaults={
                "is_active": False,
                "title": "News invitation fixture title",
                "text": self.invite_text,
                "button_text": "News invitation fixture button",
                "button_url": "https://t.me/mtproto_keys",
                "button_callback_data": "news_invitation_fixture",
                "include_payment_buttons": False,
            },
        )
        self.sorry_before = self._snapshot(
            template.objects.get(slug="sorry_server_error")
        )
        self.invite_before = self._snapshot(
            template.objects.get(slug="invite_to_channel")
        )

        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        self.apps = self.executor.loader.project_state([self.migrate_to]).apps

    def _restore_leaf_state(self) -> None:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_updates_only_sorry_server_error_support_contact(self) -> None:
        template = self.apps.get_model("notifications", "NotificationTemplate")
        sorry_after = self._snapshot(
            template.objects.get(slug="sorry_server_error")
        )
        invite_after = self._snapshot(
            template.objects.get(slug="invite_to_channel")
        )

        expected_sorry_text = self.sorry_before["text"].replace(
            "@mtproto_keys",
            "@mtprotokeys_support",
            1,
        )
        self.assertEqual(sorry_after["text"], expected_sorry_text)
        self.assertNotIn("@mtproto_keys", sorry_after["text"])
        self.assertIn("@mtprotokeys_support", sorry_after["text"])

        self.assertEqual(
            {key: value for key, value in sorry_after.items() if key != "text"},
            {
                key: value
                for key, value in self.sorry_before.items()
                if key != "text"
            },
        )
        self.assertEqual(invite_after, self.invite_before)
        self.assertIn("@mtproto_keys", invite_after["text"])
