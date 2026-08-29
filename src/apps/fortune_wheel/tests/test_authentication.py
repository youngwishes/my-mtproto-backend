from __future__ import annotations

from datetime import UTC, datetime

from django.test import SimpleTestCase
from rest_framework.exceptions import AuthenticationFailed

from apps.fortune_wheel.authentication import validate_telegram_init_data
from apps.fortune_wheel.tests.factories import make_telegram_init_data


BOT_TOKEN = "123456:test-token"
NOW = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)


class TelegramInitDataValidationTest(SimpleTestCase):
    def test_valid_signature_returns_signed_telegram_id(self) -> None:
        init_data = make_telegram_init_data(
            bot_token=BOT_TOKEN,
            user_id=1487189460,
            auth_date=int(NOW.timestamp()),
        )

        principal = validate_telegram_init_data(
            init_data=init_data,
            bot_token=BOT_TOKEN,
            now=NOW,
            max_age_seconds=3600,
        )

        self.assertEqual(principal.telegram_id, "1487189460")
        self.assertTrue(principal.is_authenticated)

    def test_modified_data_is_rejected(self) -> None:
        init_data = make_telegram_init_data(
            bot_token=BOT_TOKEN,
            user_id=1487189460,
            auth_date=int(NOW.timestamp()),
        ).replace("1487189460", "1487189461")

        with self.assertRaises(AuthenticationFailed):
            validate_telegram_init_data(
                init_data=init_data,
                bot_token=BOT_TOKEN,
                now=NOW,
                max_age_seconds=3600,
            )

    def test_data_older_than_one_hour_is_rejected(self) -> None:
        init_data = make_telegram_init_data(
            bot_token=BOT_TOKEN,
            user_id=1487189460,
            auth_date=int(NOW.timestamp()) - 3601,
        )

        with self.assertRaises(AuthenticationFailed):
            validate_telegram_init_data(
                init_data=init_data,
                bot_token=BOT_TOKEN,
                now=NOW,
                max_age_seconds=3600,
            )
