from __future__ import annotations

from django.test import SimpleTestCase

from apps.core.exceptions import BaseServiceError
from apps.vds.exceptions import KeyDoesNotExist, KeysLimitReached


class TestVDSExceptions(SimpleTestCase):
    def test_key_does_not_exist_uses_support_contact(self) -> None:
        error = KeyDoesNotExist(42)

        self.assertIsInstance(error, BaseServiceError)
        self.assertEqual(error.telegram_id, 42)
        self.assertEqual(
            error.message,
            "🔒 У вас нет активного ключа. Если вы думаете, что это ошибка, пожалуйста, "
            "напишите в поддержку: @mtprotokeys_support.",
        )
        self.assertNotIn("@mtproto_keys", error.message)

    def test_keys_limit_reached_uses_support_contact(self) -> None:
        error = KeysLimitReached(42)

        self.assertIsInstance(error, BaseServiceError)
        self.assertEqual(error.telegram_id, 42)
        self.assertIn("@mtprotokeys_support", error.message)
        self.assertNotIn("@mtproto_keys", error.message)
