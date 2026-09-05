from __future__ import annotations

from django.test import TestCase
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

    def test_page_bypasses_cached_styles_from_before_entrance_animation(self) -> None:
        response = self.client.get(reverse("fortune-wheel-page"))

        self.assertContains(response, 'fortune_wheel/styles.css?v=entrance-1')
        self.assertNotContains(response, 'fortune_wheel/styles.css"')
