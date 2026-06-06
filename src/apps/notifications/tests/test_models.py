from __future__ import annotations

from django.test import TestCase
from django.utils import timezone

from apps.notifications.enums import MailingStatus
from apps.notifications.tests.factories import MailingFactory, NotificationTemplateFactory


class TestNotificationTemplateRender(TestCase):
    def test_render_text_without_variables(self) -> None:
        template = NotificationTemplateFactory(
            text="Привет! Это тест.",
            button_text="",
            button_url="",
        )
        result = template.render()
        self.assertEqual(result.text, "Привет! Это тест.")
        self.assertIsNone(result.markup)

    def test_render_text_with_variables(self) -> None:
        template = NotificationTemplateFactory(
            text="Привет, твоя ссылка: {link}",
            button_text="",
            button_url="",
        )
        result = template.render(context={"link": "https://example.com"})
        self.assertEqual(result.text, "Привет, твоя ссылка: https://example.com")

    def test_render_with_button(self) -> None:
        template = NotificationTemplateFactory(
            text="Нажми кнопку",
            button_text="Подключиться",
            button_url="https://t.me/proxy?server={link}",
        )
        result = template.render(context={"link": "abc123"})
        self.assertEqual(result.text, "Нажми кнопку")
        self.assertIsNotNone(result.markup)
        button = result.markup.keyboard[0][0]
        self.assertEqual(button.text, "Подключиться")
        self.assertEqual(button.url, "https://t.me/proxy?server=abc123")

    def test_render_without_context_returns_raw_text(self) -> None:
        template = NotificationTemplateFactory(
            text="Текст без переменных",
            button_text="",
            button_url="",
        )
        result = template.render()
        self.assertEqual(result.text, "Текст без переменных")


class TestMailingLifecycle(TestCase):
    def test_mark_as_sending(self) -> None:
        mailing = MailingFactory(status=MailingStatus.DRAFT)
        mailing.mark_as_sending()
        mailing.refresh_from_db()
        self.assertEqual(mailing.status, MailingStatus.SENDING)

    def test_mark_as_completed(self) -> None:
        mailing = MailingFactory(status=MailingStatus.SENDING)
        mailing.mark_as_completed()
        mailing.refresh_from_db()
        self.assertEqual(mailing.status, MailingStatus.COMPLETED)
        self.assertIsNotNone(mailing.sent_at)
