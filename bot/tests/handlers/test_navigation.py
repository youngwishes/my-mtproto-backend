from __future__ import annotations

import pytest
from src.handlers.start import (
    cmd_start,
    cmd_start_inline,
    process_legal_consent,
    process_mtproxy_menu,
)
from src.messages import (
    PRODUCT_MENU_TEXT,
    SITE_URL,
    SUPPORT_URL,
    WELCOME_TEXT_MONTH,
    WELCOME_TEXT_NOT_FREE,
    WELCOME_TEXT_TWO_WEEK,
    WELCOME_TEXT_WEEK,
)

from tests.fakes import FakeCallback, FakeMessage, make_deps
from tests.handler_support import (
    FakeFreeTrial,
)


async def test_root_navigation_matches_approved_hierarchy():
    fake = FakeFreeTrial(check="MONTH")
    message = FakeMessage(text="/start", user_id=42, username="bob")

    await cmd_start(message, make_deps(free_trial=fake))

    assert fake.status_checked == ["42"]
    assert fake.checked == []
    text, markup = message.answers[0]
    assert (
        text
        == PRODUCT_MENU_TEXT
        == (
            "👋 Добро пожаловать в MTProto Keys!\n\n"
            "MTProxy, VPN, бонусы и полезные ссылки — всё здесь.\n"
            "Выбери, что тебе интересно:"
        )
    )
    expected_rows = [
        [("⚡ MTProxy", "show_mtproxy_menu", None, "success")],
        [("🔐 VPN", "show_vpn_menu", None, "primary")],
        [("🤝 Реферальная программа", "referral", None, None)],
        [("💬 Написать в поддержку", None, SUPPORT_URL, None)],
        [("Наш канал", None, "https://t.me/mtproto_keys", None)],
        [("🌐 Наш сайт", None, SITE_URL, None)],
    ]
    assert [
        [
            (button.text, button.callback_data, button.url, button.style)
            for button in row
        ]
        for row in markup.inline_keyboard
    ] == expected_rows

    consent = FakeFreeTrial(consent=False)
    consent_callback = FakeCallback(
        user_id=42,
        username="bob",
        data="accept_legal_terms",
    )
    await process_legal_consent(
        consent_callback,
        make_deps(free_trial=consent),
    )
    _, consent_markup = consent_callback.message.edits[0]
    assert [
        [
            (button.text, button.callback_data, button.url, button.style)
            for button in row
        ]
        for row in consent_markup.inline_keyboard
    ] == expected_rows

    start_callback = FakeCallback(chat_id=99, user_id=42, username="bob")
    await cmd_start_inline(start_callback)
    _, start_markup = start_callback.message.edits[0]
    assert [
        [
            (button.text, button.callback_data, button.url, button.style)
            for button in row
        ]
        for row in start_markup.inline_keyboard
    ] == expected_rows


@pytest.mark.parametrize(
    ("period", "expected_text", "boost_callback"),
    [
        ("MONTH", WELCOME_TEXT_MONTH, "boost_free"),
        ("WEEK", WELCOME_TEXT_WEEK, "boost_free"),
        ("TWO_WEEK", WELCOME_TEXT_TWO_WEEK, "boost_free"),
        ("NOT_AVAILABLE", WELCOME_TEXT_NOT_FREE, "boost_paid"),
    ],
)
async def test_mtproxy_navigation_matches_approved_hierarchy(
    period, expected_text, boost_callback
):
    fake = FakeFreeTrial(check=period)
    callback = FakeCallback(user_id=42, username="real_user")
    deps = make_deps(free_trial=fake)

    await process_mtproxy_menu(callback, deps)
    await process_mtproxy_menu(callback, deps)

    assert fake.checked == [
        ("42", "real_user", None),
        ("42", "real_user", None),
    ]
    text, markup = callback.message.edits[-1]
    assert text == expected_text
    assert text.rstrip().endswith("👇 Жми «Мои серверы» и подключайся!")
    if period == "TWO_WEEK":
        assert "По приглашению первые две недели — бесплатно." in text
        assert "Вы пришли" not in text
    assert markup.inline_keyboard[0][0].callback_data == boost_callback
    assert [
        [
            (button.text, button.callback_data, button.url, button.style)
            for button in row
        ]
        for row in markup.inline_keyboard
    ] == [
        [("⚡ Ускорить Telegram", boost_callback, None, "success")],
        [("📡 Мои серверы", "my_servers", None, "primary")],
        [("🍏 Мои яблоки", "apples_status", None, None)],
        [("🎁 Подарить MTProxy", "gift_certificate", None, None)],
        [("❓ Вопросы о MTProxy", "info", None, None)],
        [("🔙 Главное меню", "show_start_screen", None, None)],
    ]
