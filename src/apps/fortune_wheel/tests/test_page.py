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

    def test_page_does_not_render_redundant_availability_status(self) -> None:
        response = self.client.get(reverse("fortune-wheel-page"))

        self.assertNotContains(response, 'class="availability"')

    def test_page_configures_seven_and_a_half_second_spin(self) -> None:
        response = self.client.get(reverse("fortune-wheel-page"))

        self.assertContains(response, 'data-spin-duration-ms="7500"')
