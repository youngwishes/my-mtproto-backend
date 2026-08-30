from unittest import mock

from aiogram.methods import SendMessage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.custom_emoji import PremiumEmojiMiddleware


async def test_middleware_upgrades_user_message_and_button() -> None:
    method = SendMessage(
        chat_id=42,
        text="👋 <b>Привет!</b> 👇",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Обменять на 1 день — 15 🍏",
                        callback_data="redeem",
                        style="success",
                    )
                ]
            ]
        ),
    )

    async def make_request(bot, outgoing_method):
        return outgoing_method

    result = await PremiumEmojiMiddleware()(
        make_request,
        mock.Mock(),
        method,
    )

    assert result.text == (
        '<tg-emoji emoji-id="5994750571041525522">👋</tg-emoji> '
        '<b>Привет!</b> '
        '<tg-emoji emoji-id="5886451926995833684">⬇️</tg-emoji>'
    )
    button = result.reply_markup.inline_keyboard[0][0]
    assert button.text == "Обменять на 1 день — 15"
    assert button.icon_custom_emoji_id == "5818920837645867167"
    assert button.callback_data == "redeem"
    assert button.style == "success"


async def test_middleware_leaves_explicit_internal_message_unchanged() -> None:
    method = SendMessage(
        chat_id=1,
        text="⚠️ Внутреннее уведомление",
        premium_emoji=False,
    )

    async def make_request(bot, outgoing_method):
        return outgoing_method

    result = await PremiumEmojiMiddleware()(
        make_request,
        mock.Mock(),
        method,
    )

    assert result.text == "⚠️ Внутреннее уведомление"
    assert "premium_emoji" not in result.model_extra


async def test_middleware_upgrades_user_screen_for_admin_chat() -> None:
    method = SendMessage(chat_id=1, text="⚠️ Пользовательский экран")

    async def make_request(bot, outgoing_method):
        return outgoing_method

    result = await PremiumEmojiMiddleware()(
        make_request,
        mock.Mock(),
        method,
    )

    assert result.text == (
        '<tg-emoji emoji-id="5881702736843511327">⚠️</tg-emoji> '
        'Пользовательский экран'
    )


async def test_middleware_does_not_nest_existing_tags_or_change_code() -> None:
    method = SendMessage(
        chat_id=42,
        text=(
            '<tg-emoji emoji-id="5818920837645867167">🍏</tg-emoji> '
            '<code>🍏</code>'
        ),
    )

    async def make_request(bot, outgoing_method):
        return outgoing_method

    result = await PremiumEmojiMiddleware()(
        make_request,
        mock.Mock(),
        method,
    )

    assert result.text == method.text


async def test_middleware_uses_sticker_alt_without_variation_selector() -> None:
    method = SendMessage(chat_id=42, text="⚙️ Настройки")

    async def make_request(bot, outgoing_method):
        return outgoing_method

    result = await PremiumEmojiMiddleware()(
        make_request,
        mock.Mock(),
        method,
    )

    assert result.text == (
        '<tg-emoji emoji-id="5877260593903177342">⚙</tg-emoji> Настройки'
    )


async def test_middleware_replaces_back_button_with_animated_arrow() -> None:
    method = SendMessage(
        chat_id=42,
        text="Меню",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
            ]
        ),
    )

    async def make_request(bot, outgoing_method):
        return outgoing_method

    result = await PremiumEmojiMiddleware()(
        make_request,
        mock.Mock(),
        method,
    )

    button = result.reply_markup.inline_keyboard[0][0]
    assert button.text == "Назад"
    assert button.icon_custom_emoji_id == "5875082500023258804"
