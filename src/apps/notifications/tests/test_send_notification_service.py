from __future__ import annotations

from unittest import mock

from django.test import TestCase

from apps.notifications.services.send_notification_service import SendNotificationService
from apps.notifications.tests.factories import NotificationTemplateFactory


class TestSendNotificationService(TestCase):
    @mock.patch("apps.notifications.services.send_notification_service.send_telegram_message")
    def test_sends_rendered_template(self, mock_send: mock.Mock) -> None:
        NotificationTemplateFactory(
            slug="test-notify",
            text="Привет, ссылка: {link}",
            button_text="Подключиться",
            button_url="{link}",
        )

        service = SendNotificationService(
            slug="test-notify",
            context={"link": "https://example.com"},
        )
        service(chat_id=123)

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["chat_id"], 123)
        self.assertIn("https://example.com", call_kwargs["text"])
        self.assertIsNotNone(call_kwargs["markup"])

    @mock.patch("apps.notifications.services.send_notification_service.send_telegram_message")
    def test_sends_template_without_button(self, mock_send: mock.Mock) -> None:
        NotificationTemplateFactory(
            slug="no-button",
            text="Простое сообщение",
            button_text="",
            button_url="",
        )

        service = SendNotificationService(slug="no-button", context={})
        service(chat_id=456)

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["text"], "Простое сообщение")
        self.assertIsNone(call_kwargs["markup"])
