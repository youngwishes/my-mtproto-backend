from __future__ import annotations

from django.test import SimpleTestCase

from apps.core.exceptions import BaseServiceError
from apps.users.exceptions import AlreadyUsedFree


class TestUserExceptions(SimpleTestCase):
    def test_already_used_free_uses_support_contact(self) -> None:
        error = AlreadyUsedFree(42)

        self.assertIsInstance(error, BaseServiceError)
        self.assertEqual(error.telegram_id, 42)
        self.assertEqual(
            error.message,
            "🔒 Вы уже получили беплатную ссылку. Если она не работает — "
            "напишите в поддержку: @mtprotokeys_support.",
        )
        self.assertNotIn("@mtproto_keys", error.message)
