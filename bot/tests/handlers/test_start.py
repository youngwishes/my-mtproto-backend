from __future__ import annotations

import pytest
from src.domains.free_trial import FreeTrialKey
from src.exceptions import (
    APIError,
)
from src.handlers.free_trial import process_boost_free
from src.handlers.start import (
    cmd_start,
    cmd_start_inline,
    process_info,
    process_legal_consent,
    process_mtproxy_menu,
)
from src.messages import (
    KEY_GENERATED_TEXT,
    PRIVACY_URL,
    PRODUCT_MENU_TEXT,
    TERMS_URL,
)

from tests.fakes import FakeCallback, FakeMessage, make_deps
from tests.handler_support import (
    FakeFreeTrial,
)


async def test_cmd_start_passes_none_username_as_none_not_string():
    # У юзера нет @username в Telegram → шлём None, а не str(None) == "None"
    fake = FakeFreeTrial(check="MONTH")
    callback = FakeCallback(user_id=42, username=None)

    await process_mtproxy_menu(callback, make_deps(free_trial=fake))

    assert fake.checked == [("42", None, None)]


async def test_cmd_start_ignores_self_referral():
    fake = FakeFreeTrial(consent=False)
    message = FakeMessage(text="/start 42", user_id=42)

    await cmd_start(message, make_deps(free_trial=fake))

    _, markup = message.answers[0]
    assert markup.inline_keyboard[0][0].callback_data == "accept_legal_terms"


async def test_cmd_start_shows_consent_without_registering_new_user():
    fake = FakeFreeTrial(consent=False)
    message = FakeMessage(text="/start", user_id=42)

    await cmd_start(message, make_deps(free_trial=fake))

    assert fake.status_checked == ["42"]
    assert fake.checked == []
    text, markup = message.answers[0]
    assert "Для использования сервиса необходимо принять" in text
    assert "вы принимаете" not in text
    assert TERMS_URL in text
    assert PRIVACY_URL in text
    assert len(markup.inline_keyboard) == 1
    assert markup.inline_keyboard[0][0].callback_data == "accept_legal_terms"


async def test_cmd_start_carries_referrer_in_consent_callback():
    fake = FakeFreeTrial(consent=False)
    message = FakeMessage(text="/start 777", user_id=42)

    await cmd_start(message, make_deps(free_trial=fake))

    _, markup = message.answers[0]
    assert markup.inline_keyboard[0][0].callback_data == "accept_legal_terms:777"


async def test_accept_consent_registers_clicking_user_and_opens_start_screen():
    fake = FakeFreeTrial(consent=False)
    callback = FakeCallback(
        user_id=42,
        username="real_user",
        data="accept_legal_terms:777",
    )

    await process_legal_consent(callback, make_deps(free_trial=fake))

    assert fake.accepted == [("42", "real_user", "777")]
    assert fake.checked == []
    text, markup = callback.message.edits[0]
    assert text == PRODUCT_MENU_TEXT
    assert [[button.text for button in row] for row in markup.inline_keyboard] == [
        ["⚡ MTProxy"],
        ["🔐 VPN"],
        ["🤝 Реферальная программа"],
        ["💬 Написать в поддержку"],
        ["📣 Наш канал"],
        ["📜 Условия пользования", "🔒 Политика конфиденциальности"],
    ]


async def test_accept_consent_does_not_open_menu_when_backend_returns_false():
    fake = FakeFreeTrial(consent=False, accept_result=False)
    callback = FakeCallback(user_id=42, data="accept_legal_terms")

    with pytest.raises(APIError):
        await process_legal_consent(callback, make_deps(free_trial=fake))

    assert fake.checked == []
    assert callback.message.edits == []


async def test_show_start_screen_answers_callback():
    # «🔙 Назад» (show_start_screen) must close the loading spinner in Telegram
    callback = FakeCallback(chat_id=42)

    await cmd_start_inline(callback)

    assert callback.answers, "callback.answer() was not called — spinner hangs"


async def test_show_start_screen_shows_product_root():
    callback = FakeCallback(chat_id=99, user_id=42, username="real_user")

    await cmd_start_inline(callback)

    text, markup = callback.message.edits[0]
    assert text == PRODUCT_MENU_TEXT
    assert [
        [button.callback_data for button in row] for row in markup.inline_keyboard
    ] == [
        ["show_mtproxy_menu"],
        ["show_vpn_menu"],
        ["referral"],
        [None],
        [None],
        [None, None],
    ]


async def test_info_answers_callback():
    callback = FakeCallback(chat_id=42)

    await process_info(callback)

    assert callback.answers
    text, _ = callback.message.edits[0]
    assert (
        "Прокси помогает Telegram работать стабильнее и уменьшает потери при плохом "
        "интернете, защищает трафик. Максимальная скорость зависит от твоего интернета."
        in text
    )
    assert "обходит ограничения" not in text
    assert "блокировок" not in text
    assert "99 ★" in text
    assert "80 ★" not in text
    assert "@mtproto_keys" in KEY_GENERATED_TEXT


async def test_boost_free_claims_key_and_shows_expiry():
    fake = FakeFreeTrial(key=FreeTrialKey(expired_date="2026-08-01"))
    callback = FakeCallback(chat_id=42)

    await process_boost_free(callback, make_deps(free_trial=fake))

    assert fake.claimed == ["42"]
    text, _ = callback.message.edits[0]
    assert "01.08.2026" in text
    assert "2026-08-01" not in text
    assert text.rstrip().endswith("👇 Нажми «Мои серверы» ниже")


@pytest.mark.parametrize(
    ("balance", "days", "missing", "has_key", "expected", "first_action"),
    [
        (37, 2, 0, True, "Доступно дней: <b>2</b>", "apples_redeem_one"),
        (5, 0, 10, True, "Для обмена не хватает <b>10 🍏</b>", "apples_status"),
        (25, 1, 0, False, "существующего MTProxy-ключа", "apples_status"),
    ],
)
async def test_start_apples_spend_opens_exchange_without_spending(
    balance,
    days,
    missing,
    has_key,
    expected,
    first_action,
):
    from src.domains.payments import AppleStatus
    from tests.handler_support import FakePayments

    payments = FakePayments(
        apple_status=AppleStatus(
            balance=balance,
            eligible_purchase_count=0,
            level="Росток",
            rate_percent=5,
            next_level_purchase_count=3,
            purchases_to_next_level=3,
            is_max_level=False,
            redeemable_days=days,
            missing_apples=missing,
            has_existing_key=has_key,
        )
    )
    message = FakeMessage(text="/start apples_spend", user_id=42)

    await cmd_start(
        message,
        make_deps(
            free_trial=FakeFreeTrial(consent=True),
            payments=payments,
        ),
    )

    text, markup = message.answers[0]
    assert expected in text
    assert markup.inline_keyboard[0][0].callback_data == first_action
    assert payments.apple_status_calls == [42]
    assert payments.apple_preview_calls == []
    assert payments.apple_confirm_calls == []


async def test_start_apples_spend_requires_consent():
    message = FakeMessage(text="/start apples_spend", user_id=42)

    await cmd_start(message, make_deps(free_trial=FakeFreeTrial(consent=False)))

    text, markup = message.answers[0]
    assert "Для использования сервиса необходимо принять" in text
    assert markup.inline_keyboard[0][0].callback_data == "accept_legal_terms"
