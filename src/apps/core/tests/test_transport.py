from __future__ import annotations

from unittest import mock

from django.test import TestCase, override_settings
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

from apps.core.telegram.custom_emoji import _CUSTOM_EMOJI


_STATIC_CUSTOM_EMOJI_IDS = {
    "5776375003280838798",
    "5778527486270770928",
    "5778605968208170641",
    "5818920837645867167",
    "5823268688874179761",
    "5839200986022812209",
    "5843553939672274145",
    "5845947563601041174",
    "5873121512445187130",
    "5874986954180791957",
    "5875082500023258804",
    "5877260593903177342",
    "5877465816030515018",
    "5877468380125990242",
    "5879585266426973039",
    "5881702736843511327",
    "5886330010054168711",
    "5886451926995833684",
    "5886666250158870040",
    "5897850551156084824",
    "5915556996215476302",
    "5958376256788502078",
    "5963312935148195483",
    "5967412305338568701",
    "5967548335542767952",
    "5985817223749439505",
    "5985833664884250583",
    "5994502837327892086",
    "5994750571041525522",
    "6005570495603282482",
    "6005843436479975944",
    "6008118472066732010",
    "6032937473162614352",
}


class TestPremiumEmojiCatalog(TestCase):
    def test_excludes_static_custom_emoji(self) -> None:
        selected_ids = {emoji_id for emoji_id, _ in _CUSTOM_EMOJI.values()}

        self.assertTrue(selected_ids.isdisjoint(_STATIC_CUSTOM_EMOJI_IDS))


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
            '<tg-emoji emoji-id="5472055112702629499">👋</tg-emoji> '
            'Привет '
            '<tg-emoji emoji-id="5470177992950946662">👇</tg-emoji>',
        )
        button = call["reply_markup"].keyboard[0][0]
        self.assertEqual(button.text, "Обменять на 1 день — 15 🍏")
        self.assertIsNone(button.icon_custom_emoji_id)
        self.assertEqual(button.callback_data, "redeem")
        self.assertEqual(button.style, "success")

    @mock.patch("apps.core.telegram.transport.bot")
    def test_send_keeps_green_apple_standard(self, mock_bot: mock.Mock) -> None:
        from apps.core.telegram.transport import send_telegram_message

        send_telegram_message(chat_id=123, text="15 🍏")

        self.assertEqual(
            mock_bot.send_message.call_args.kwargs["text"],
            "15 🍏",
        )

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
    def test_send_uses_sticker_alt(
        self,
        mock_bot: mock.Mock,
    ) -> None:
        from apps.core.telegram.transport import send_telegram_message

        send_telegram_message(chat_id=123, text="⚙️ Настройки")

        self.assertEqual(
            mock_bot.send_message.call_args.kwargs["text"],
            '<tg-emoji emoji-id="5357427684022453456">⚙️</tg-emoji> Настройки',
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
            "5393368163628905240",
        )

    @mock.patch("apps.core.telegram.transport.bot")
    def test_send_animates_finland_kazakhstan_and_usa_flags(
        self,
        mock_bot: mock.Mock,
    ) -> None:
        from apps.core.telegram.transport import send_telegram_message

        markup = InlineKeyboardMarkup(
            keyboard=[
                [InlineKeyboardButton(text="🇫🇮 Подключиться", callback_data="fi")]
            ]
        )

        send_telegram_message(
            chat_id=123,
            text="🇫🇮 Финляндия · 🇰🇿 Казахстан · 🇺🇸 США",
            markup=markup,
        )

        call = mock_bot.send_message.call_args.kwargs
        self.assertEqual(
            call["text"],
            '<tg-emoji emoji-id="5382151560182642075">🇫🇮</tg-emoji> Финляндия · '
            '<tg-emoji emoji-id="5228718354658769982">🇰🇿</tg-emoji> Казахстан · '
            '<tg-emoji emoji-id="5202021044105257611">🇺🇸</tg-emoji> США',
        )
        button = call["reply_markup"].keyboard[0][0]
        self.assertEqual(button.text, "Подключиться")
        self.assertEqual(
            button.icon_custom_emoji_id,
            "5382151560182642075",
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
