from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.fortune_wheel.models import FortuneSpin
from apps.fortune_wheel.tests.factories import make_telegram_init_data
from apps.users.tests.factories import SystemUserFactory


BOT_TOKEN = "123456:test-token"


@override_settings(
    BOT_TOKEN=BOT_TOKEN,
    BOT_LINK="https://t.me/test_proxy_bot",
    FORTUNE_WHEEL_INIT_DATA_MAX_AGE_SECONDS=3600,
)
class FortuneWheelAPITest(TestCase):
    def headers(self, *, user_id: int = 1487189460) -> dict[str, str]:
        init_data = make_telegram_init_data(
            bot_token=BOT_TOKEN,
            user_id=user_id,
            auth_date=int(timezone.now().timestamp()),
        )
        return {"Telegram-Init-Data": init_data}

    def test_status_allows_first_spin_for_registered_user(self) -> None:
        SystemUserFactory(
            username="1487189460",
            legal_terms_accepted=True,
        )

        response = self.client.post(
            reverse("fortune-wheel-status"),
            data={},
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "registered": True,
                "can_spin": True,
                "last_prize": None,
                "next_spin_at": None,
                "registration_url": None,
            },
        )

    def test_unknown_user_gets_bot_registration_link(self) -> None:
        response = self.client.post(
            reverse("fortune-wheel-status"),
            data={},
            headers=self.headers(user_id=777),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["registered"], False)
        self.assertEqual(
            response.json()["registration_url"],
            "https://t.me/test_proxy_bot",
        )

    def test_invalid_telegram_signature_is_forbidden(self) -> None:
        response = self.client.post(
            reverse("fortune-wheel-status"),
            data={},
            headers={"Telegram-Init-Data": "auth_date=1&hash=invalid"},
        )

        self.assertEqual(response.status_code, 403)

    def test_spin_returns_server_prize_and_immediate_repeat_is_conflict(self) -> None:
        user = SystemUserFactory(
            username="1487189460",
            legal_terms_accepted=True,
            apple_balance=7,
        )

        with patch(
            "apps.fortune_wheel.services.spin.secrets.randbelow", return_value=95
        ):
            first = self.client.post(
                reverse("fortune-wheel-spin"),
                data={},
                headers=self.headers(),
            )
            repeated = self.client.post(
                reverse("fortune-wheel-spin"),
                data={},
                headers=self.headers(),
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["prize_apples"], 60)
        self.assertIn("spun_at", first.json())
        self.assertIn("next_spin_at", first.json())
        self.assertEqual(repeated.status_code, 409)
        self.assertEqual(repeated.json()["last_prize"], 60)
        user.refresh_from_db()
        self.assertEqual(user.apple_balance, 67)
        self.assertEqual(FortuneSpin.objects.filter(user=user).count(), 1)
