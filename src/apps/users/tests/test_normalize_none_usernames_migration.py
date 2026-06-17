from __future__ import annotations

from importlib import import_module

from django.apps import apps
from django.test import TestCase

from apps.users.tests.factories import SystemUserFactory

normalize_none_usernames = import_module(
    "apps.users.migrations.0016_normalize_none_usernames"
).normalize_none_usernames


class TestNormalizeNoneUsernamesMigration(TestCase):
    def test_literal_none_telegram_username_becomes_blank(self) -> None:
        user = SystemUserFactory(telegram_username="None")

        normalize_none_usernames(apps, None)

        user.refresh_from_db()
        self.assertEqual(user.telegram_username, "")

    def test_literal_none_invited_from_becomes_null(self) -> None:
        user = SystemUserFactory(invited_from_username="None")

        normalize_none_usernames(apps, None)

        user.refresh_from_db()
        self.assertIsNone(user.invited_from_username)

    def test_real_values_untouched(self) -> None:
        user = SystemUserFactory(
            telegram_username="@durov", invited_from_username="123"
        )

        normalize_none_usernames(apps, None)

        user.refresh_from_db()
        self.assertEqual(user.telegram_username, "@durov")
        self.assertEqual(user.invited_from_username, "123")
