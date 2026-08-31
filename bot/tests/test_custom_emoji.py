from unittest import mock

from aiogram.methods import SendMessage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.custom_emoji import _CUSTOM_EMOJI, PremiumEmojiMiddleware


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


def test_catalog_excludes_static_custom_emoji() -> None:
    selected_ids = {emoji_id for emoji_id, _ in _CUSTOM_EMOJI.values()}

    assert selected_ids.isdisjoint(_STATIC_CUSTOM_EMOJI_IDS)


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
        '<tg-emoji emoji-id="5472055112702629499">👋</tg-emoji> '
        '<b>Привет!</b> '
        '<tg-emoji emoji-id="5470177992950946662">👇</tg-emoji>'
    )
    button = result.reply_markup.inline_keyboard[0][0]
    assert button.text == "Обменять на 1 день — 15 🍏"
    assert button.icon_custom_emoji_id is None
    assert button.callback_data == "redeem"
    assert button.style == "success"


async def test_middleware_keeps_green_apple_standard() -> None:
    method = SendMessage(chat_id=42, text="15 🍏")

    async def make_request(bot, outgoing_method):
        return outgoing_method

    result = await PremiumEmojiMiddleware()(
        make_request,
        mock.Mock(),
        method,
    )

    assert result.text == "15 🍏"


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
        '<tg-emoji emoji-id="5467519850576354798">❕</tg-emoji> '
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


async def test_middleware_uses_sticker_alt() -> None:
    method = SendMessage(chat_id=42, text="⚙️ Настройки")

    async def make_request(bot, outgoing_method):
        return outgoing_method

    result = await PremiumEmojiMiddleware()(
        make_request,
        mock.Mock(),
        method,
    )

    assert result.text == (
        '<tg-emoji emoji-id="5357427684022453456">⚙️</tg-emoji> Настройки'
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
    assert button.icon_custom_emoji_id == "5393368163628905240"


async def test_middleware_animates_finland_kazakhstan_and_usa_flags() -> None:
    method = SendMessage(
        chat_id=42,
        text="🇫🇮 Финляндия · 🇰🇿 Казахстан · 🇺🇸 США",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🇫🇮 Подключиться", callback_data="fi")]
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
        '<tg-emoji emoji-id="5382151560182642075">🇫🇮</tg-emoji> Финляндия · '
        '<tg-emoji emoji-id="5228718354658769982">🇰🇿</tg-emoji> Казахстан · '
        '<tg-emoji emoji-id="5202021044105257611">🇺🇸</tg-emoji> США'
    )
    button = result.reply_markup.inline_keyboard[0][0]
    assert button.text == "Подключиться"
    assert button.icon_custom_emoji_id == "5382151560182642075"
