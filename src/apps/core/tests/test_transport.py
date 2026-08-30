from __future__ import annotations

from unittest import mock

from django.test import TestCase, override_settings
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup


class TestSend(TestCase):
    @mock.patch("apps.core.telegram.transport.bot")
    def test_send_upgrades_user_message_and_button(self, mock_bot: mock.Mock) -> None:
        from apps.core.telegram.transport import send_telegram_message

        markup = InlineKeyboardMarkup(
            keyboard=[
                [
                    InlineKeyboardButton(
                        text="Обменять на 1 день — 15 🍏",
                        callback_data="redeem",
                        style="success",
                    )
                ]
            ]
        )

        send_telegram_message(chat_id=123, text="👋 Привет 👇", markup=markup)

        call = mock_bot.send_message.call_args.kwargs
        self.assertEqual(
            call["text"],
            '<tg-emoji emoji-id="5994750571041525522">👋</tg-emoji> '
            'Привет '
            '<tg-emoji emoji-id="5886451926995833684">⬇️</tg-emoji>',
        )
        button = call["reply_markup"].keyboard[0][0]
        self.assertEqual(button.text, "Обменять на 1 день — 15")
        self.assertEqual(
            button.icon_custom_emoji_id,
            "5818920837645867167",
        )
        self.assertEqual(button.callback_data, "redeem")
        self.assertEqual(button.style, "success")

    @mock.patch("apps.core.telegram.transport.bot")
    def test_send_can_keep_internal_message_unchanged(self, mock_bot: mock.Mock) -> None:
        from apps.core.telegram.transport import send_telegram_message

        send_telegram_message(
            chat_id=123,
            text="⚠️ Внутреннее уведомление",
            premium_emoji=False,
        )

        self.assertEqual(
            mock_bot.send_message.call_args.kwargs["text"],
            "⚠️ Внутреннее уведомление",
        )

    @mock.patch("apps.core.telegram.transport.bot")
    def test_send_uses_sticker_alt_without_variation_selector(
        self,
        mock_bot: mock.Mock,
    ) -> None:
        from apps.core.telegram.transport import send_telegram_message

        send_telegram_message(chat_id=123, text="⚙️ Настройки")

        self.assertEqual(
            mock_bot.send_message.call_args.kwargs["text"],
            '<tg-emoji emoji-id="5877260593903177342">⚙</tg-emoji> Настройки',
        )

    @mock.patch("apps.core.telegram.transport.bot")
    def test_send_replaces_back_button_with_animated_arrow(
        self,
        mock_bot: mock.Mock,
    ) -> None:
        from apps.core.telegram.transport import send_telegram_message

        markup = InlineKeyboardMarkup(
            keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
            ]
        )

        send_telegram_message(chat_id=123, text="Меню", markup=markup)

        button = mock_bot.send_message.call_args.kwargs["reply_markup"].keyboard[0][0]
        self.assertEqual(button.text, "Назад")
        self.assertEqual(
            button.icon_custom_emoji_id,
            "5875082500023258804",
        )

    @mock.patch("apps.core.telegram.transport.bot")
    def test_send_calls_bot_send_message_with_defaults(self, mock_bot: mock.Mock) -> None:
        from apps.core.telegram.transport import send_telegram_message

        send_telegram_message(chat_id=123, text="hello")

        mock_bot.send_message.assert_called_once_with(
            chat_id=123,
            text="hello",
            parse_mode="HTML",
            reply_markup=None,
            timeout=None,
        )

    @mock.patch("apps.core.telegram.transport.bot")
    def test_send_passes_markup_and_timeout(self, mock_bot: mock.Mock) -> None:
        from apps.core.telegram.transport import send_telegram_message

        markup = InlineKeyboardMarkup()
        send_telegram_message(chat_id=456, text="test", markup=markup, timeout=10)

        mock_bot.send_message.assert_called_once_with(
            chat_id=456,
            text="test",
            parse_mode="HTML",
            reply_markup=markup,
            timeout=10,
        )

    @mock.patch("apps.core.telegram.transport.bot")
    def test_send_custom_parse_mode(self, mock_bot: mock.Mock) -> None:
        from apps.core.telegram.transport import send_telegram_message

        send_telegram_message(chat_id=789, text="**bold**", parse_mode="Markdown")

        mock_bot.send_message.assert_called_once_with(
            chat_id=789,
            text="**bold**",
            parse_mode="Markdown",
            reply_markup=None,
            timeout=None,
        )


class TestIsChannelMember(TestCase):
    @mock.patch("apps.core.telegram.transport.bot")
    @override_settings(TELEGRAM_CHANNEL_ID="-100123")
    def test_returns_true_for_member(self, mock_bot: mock.Mock) -> None:
        from apps.core.telegram.transport import is_channel_member

        mock_member = mock.Mock()
        mock_member.status = "member"
        mock_bot.get_chat_member.return_value = mock_member

        result = is_channel_member(telegram_id=111)

        self.assertTrue(result)
        mock_bot.get_chat_member.assert_called_once_with(
            chat_id="-100123", user_id=111,
        )

    @mock.patch("apps.core.telegram.transport.bot")
    @override_settings(TELEGRAM_CHANNEL_ID="-100123")
    def test_returns_true_for_administrator(self, mock_bot: mock.Mock) -> None:
        from apps.core.telegram.transport import is_channel_member

        mock_member = mock.Mock()
        mock_member.status = "administrator"
        mock_bot.get_chat_member.return_value = mock_member

        self.assertTrue(is_channel_member(telegram_id=222))

    @mock.patch("apps.core.telegram.transport.bot")
    @override_settings(TELEGRAM_CHANNEL_ID="-100123")
    def test_returns_false_for_left(self, mock_bot: mock.Mock) -> None:
        from apps.core.telegram.transport import is_channel_member

        mock_member = mock.Mock()
        mock_member.status = "left"
        mock_bot.get_chat_member.return_value = mock_member

        self.assertFalse(is_channel_member(telegram_id=333))
