from __future__ import annotations

from django.test import TestCase, override_settings
from django.urls import reverse


class FortuneWheelPageTest(TestCase):
    def test_page_exposes_branded_wheel_ui_and_telegram_bridge(self) -> None:
        response = self.client.get(reverse("fortune-wheel-page"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Колесо фортуны")
        self.assertContains(response, "Крутить колесо")
        self.assertContains(response, "telegram-web-app.js")
        self.assertContains(response, "fortune_wheel/wheel-disc.png")
        self.assertNotContains(response, "20%")
        self.assertNotContains(response, "30%")

    def test_page_keeps_hidden_compatibility_hook_without_status_copy(self) -> None:
        response = self.client.get(reverse("fortune-wheel-page"))

        self.assertContains(response, '<p class="availability" hidden></p>', html=True)
        self.assertNotContains(response, "Вращение доступно сейчас")
        self.assertNotContains(response, "Следующая попытка ещё не доступна")

    def test_page_configures_full_animation_for_reduced_motion(self) -> None:
        response = self.client.get(reverse("fortune-wheel-page"))

        self.assertContains(response, 'data-spin-duration-ms="7500"')
        self.assertContains(response, 'data-reduced-spin-duration-ms="7500"')

    def test_page_bypasses_cached_assets_from_before_reward_animation(self) -> None:
        response = self.client.get(reverse("fortune-wheel-page"))

        self.assertContains(response, "fortune_wheel/styles.css?v=reward-1")
        self.assertNotContains(response, 'fortune_wheel/styles.css"')
        self.assertContains(response, "fortune_wheel/app.js?v=reward-1")

    @override_settings(BOT_LINK="https://t.me/test_wheel_bot")
    def test_page_links_reward_to_bot_exchange(self) -> None:
        response = self.client.get(reverse("fortune-wheel-page"))

        self.assertContains(
            response, 'href="https://t.me/test_wheel_bot?start=apples_spend"'
        )
        self.assertContains(response, "🍏 Потратить яблоки")
        self.assertContains(response, "15 🍏 = 1 день MTProxy")
