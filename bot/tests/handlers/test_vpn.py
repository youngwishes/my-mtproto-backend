from __future__ import annotations

from __future__ import annotations


import pytest


from aiogram.types import LabeledPrice


from src.exceptions import (
    APIError,
    VPNReissueRequiresRenewal,
    VPNSubscriptionDoesNotExist,
)


from src.handlers.vpn import (
    process_vpn,
    process_vpn_menu,
    process_vpn_pay_stars,
    process_vpn_reissue,
    process_vpn_reissue_confirm,
    process_vpn_subscription,
)


from src.messages import (
    VPN_REISSUE_CONFIRM_TEXT,
    VPN_REISSUE_DONE_BANNER,
)


from src.domains.payments import (
    StarsInvoice,
)


from src.domains.vpn import VPNMenu, VPNReissue


from tests.fakes import FakeBot, FakeCallback

from tests.handler_support import (
    APPROVED_VPN_PAYMENT_TEXT,
    FakePayments,
    FakeVPN,
    _deps_with_vpn,
)


async def test_vpn_navigation_matches_approved_hierarchy():
    callback = FakeCallback(data="show_vpn_menu")

    await process_vpn_menu(callback)

    assert callback.answers
    text, markup = callback.message.edits[0]
    assert (
        text
        == """🔐 <b>VPN от MTProto Keys</b>

🌐 Защищённое подключение к интернету
📱 Работает на Android, iOS, Windows и macOS
🔗 Постоянная subscription-ссылка
⚙️ Подключение через приложение HAPP

👇 Выбери действие:"""
    )
    assert [
        [
            (
                button.text,
                button.callback_data,
                button.url,
                button.style,
            )
            for button in row
        ]
        for row in markup.inline_keyboard
    ] == [
        [("💳 Купить или продлить VPN", "vpn", None, "success")],
        [("🔑 Моя подписка", "vpn_subscription", None, "primary")],
        [
            (
                "📖 Как подключить VPN",
                None,
                "https://mtprotokeys.com/vpn/",
                None,
            )
        ],
        [("🔙 Главное меню", "show_start_screen", None, None)],
    ]


async def test_vpn_purchase_fetches_stars_invoice_and_shows_stars_only_screen():
    callback = FakeCallback(chat_id=42, user_id=42, data="vpn")
    vpn = FakeVPN(
        menu=VPNMenu(
            status="active",
            expired_at="2026-08-31T12:00:00+00:00",
            subscription_url="https://vpn.example/subscriptions/token/",
        )
    )
    stars = StarsInvoice(
        title="VPN на месяц",
        description="VPN-подписка",
        prices=[LabeledPrice(label="VPN на месяц", amount=237)],
        rub_amount="149.00",
        payment_methods=("stars", "crypto_pay"),
        priority_payment_methods=(),
    )
    deps = _deps_with_vpn(
        vpn=vpn,
        payments=FakePayments(stars=stars),
    )

    await process_vpn(callback, deps)

    assert callback.answers
    assert vpn.menu_calls == []
    assert deps.payments.vpn_stars_invoice_calls == 1
    text, markup = callback.message.edits[0]
    assert text == APPROVED_VPN_PAYMENT_TEXT
    assert "https://vpn.example/subscriptions/token/" not in text
    assert [
        [button.callback_data for button in row] for row in markup.inline_keyboard
    ] == [
        ["vpn_pay_stars"],
        ["vpn_pay_crypto"],
        ["show_vpn_menu"],
    ]
    assert markup.inline_keyboard[0][0].text == "⭐ Telegram Stars — 237 ★"


@pytest.mark.parametrize(
    ("menu", "expected_text", "expected_rows"),
    [
        (
            VPNMenu(
                status="active",
                expired_at="2026-08-31T22:30:00+00:00",
                subscription_url="https://vpn.example/subscriptions/active/",
            ),
            """🔐 <b>Твоя VPN-подписка активна</b>

Действует до: <b>01.09.2026</b>

Subscription-ссылка:
<code>https://vpn.example/subscriptions/active/</code>""",
            [
                [("🔄 Перевыпустить ссылку", "vpn_reissue", "primary")],
                [("🔙 Назад", "show_vpn_menu", None)],
            ],
        ),
        (
            VPNMenu(
                status="expired",
                expired_at="2026-07-31T12:00:00+00:00",
                subscription_url="https://vpn.example/subscriptions/expired/",
            ),
            """🔐 <b>VPN-подписка закончилась</b>

Она действовала до: <b>31.07.2026</b>

Subscription-ссылка:
<code>https://vpn.example/subscriptions/expired/</code>""",
            [
                [("💳 Продлить VPN", "vpn", "success")],
                [("🔄 Перевыпустить ссылку", "vpn_reissue", "primary")],
                [("🔙 Назад в VPN", "show_vpn_menu", None)],
            ],
        ),
    ],
)
async def test_vpn_subscription_navigation_matches_status(
    menu,
    expected_text,
    expected_rows,
):
    callback = FakeCallback(chat_id=42, user_id=42, data="vpn_subscription")
    vpn = FakeVPN(menu=menu)
    deps = _deps_with_vpn(vpn=vpn)

    await process_vpn_subscription(callback, deps)

    assert callback.answers
    assert vpn.menu_calls == ["42"]
    assert deps.payments.vpn_stars_invoice_calls == 0
    text, markup = callback.message.edits[0]
    assert text == expected_text
    assert [
        [(button.text, button.callback_data, button.style) for button in row]
        for row in markup.inline_keyboard
    ] == expected_rows


async def test_vpn_subscription_without_subscription_keeps_menu_and_raises_error():
    callback = FakeCallback(chat_id=42, user_id=42, data="vpn_subscription")
    vpn = FakeVPN(menu=VPNMenu(status="none", expired_at=None, subscription_url=None))
    deps = _deps_with_vpn(vpn=vpn)

    with pytest.raises(VPNSubscriptionDoesNotExist) as exc_info:
        await process_vpn_subscription(callback, deps)

    assert callback.answers
    assert vpn.menu_calls == ["42"]
    assert deps.payments.vpn_stars_invoice_calls == 0
    assert callback.message.edits == []
    assert exc_info.value.telegram_id == "42"
    assert exc_info.value.message == (
        "🔒 У тебя нет активной VPN-подписки. Если думаешь, что это ошибка, "
        "пожалуйста, напиши в поддержку: @mtprotokeys_support."
    )
    assert "@mtproto_keys" not in exc_info.value.message


async def test_vpn_reissue_status_gate_and_confirmation():
    expired_callback = FakeCallback(chat_id=42, user_id=42, data="vpn_reissue")
    expired_vpn = FakeVPN(
        menu=VPNMenu(
            status="expired",
            expired_at="2026-07-31T12:00:00+00:00",
            subscription_url="https://vpn.example/subscriptions/expired/",
        )
    )

    with pytest.raises(VPNReissueRequiresRenewal) as exc_info:
        await process_vpn_reissue(expired_callback, _deps_with_vpn(vpn=expired_vpn))

    assert exc_info.value.telegram_id == "42"
    assert exc_info.value.message == (
        "🔒 Перевыпуск VPN-ссылки доступен только после продления подписки."
    )
    assert expired_vpn.menu_calls == ["42"]
    assert expired_vpn.reissue_calls == []
    assert expired_callback.message.edits == []

    active_callback = FakeCallback(chat_id=42, user_id=42, data="vpn_reissue")
    active_vpn = FakeVPN(
        menu=VPNMenu(
            status="active",
            expired_at="2026-08-31T12:00:00+00:00",
            subscription_url="https://vpn.example/subscriptions/active/",
        )
    )

    await process_vpn_reissue(active_callback, _deps_with_vpn(vpn=active_vpn))

    assert active_vpn.menu_calls == ["42"]
    assert active_vpn.reissue_calls == []
    text, markup = active_callback.message.edits[0]
    assert text == VPN_REISSUE_CONFIRM_TEXT
    assert [
        [(button.text, button.callback_data, button.style) for button in row]
        for row in markup.inline_keyboard
    ] == [
        [("✅ Да, перевыпустить", "vpn_reissue_confirm", "primary")],
        [("🔙 Отмена", "vpn_subscription", None)],
    ]


async def test_vpn_reissue_without_subscription_keeps_menu_and_raises_error():
    callback = FakeCallback(chat_id=42, user_id=42, data="vpn_reissue")
    vpn = FakeVPN(menu=VPNMenu(status="none", expired_at=None, subscription_url=None))

    with pytest.raises(VPNSubscriptionDoesNotExist) as exc_info:
        await process_vpn_reissue(callback, _deps_with_vpn(vpn=vpn))

    assert callback.answers
    assert vpn.menu_calls == ["42"]
    assert vpn.reissue_calls == []
    assert callback.message.edits == []
    assert exc_info.value.telegram_id == "42"
    assert exc_info.value.message == (
        "🔒 У тебя нет активной VPN-подписки. Если думаешь, что это ошибка, "
        "пожалуйста, напиши в поддержку: @mtprotokeys_support."
    )


async def test_vpn_reissue_cancel_reloads_without_mutation():
    callback = FakeCallback(chat_id=42, user_id=42, data="vpn_subscription")
    vpn = FakeVPN(
        menu=VPNMenu(
            status="active",
            expired_at="2026-08-31T12:00:00+00:00",
            subscription_url="https://vpn.example/subscriptions/active/",
        )
    )

    await process_vpn_subscription(callback, _deps_with_vpn(vpn=vpn))

    assert vpn.events == ["menu"]
    assert vpn.reissue_calls == []
    assert "https://vpn.example/subscriptions/active/" in callback.message.edits[0][0]


async def test_vpn_reissue_success_reloads_menu_with_banner():
    callback = FakeCallback(chat_id=42, user_id=42, data="vpn_reissue_confirm")
    vpn = FakeVPN(
        menu=VPNMenu(
            status="active",
            expired_at="2026-08-31T12:00:00+00:00",
            subscription_url="https://vpn.example/subscriptions/new-token/",
        ),
        reissue=VPNReissue(
            expired_at="2026-08-31T12:00:00+00:00",
            subscription_url="https://vpn.example/subscriptions/result-token/",
        ),
    )

    await process_vpn_reissue_confirm(callback, _deps_with_vpn(vpn=vpn))

    assert vpn.events == ["reissue", "menu"]
    assert vpn.reissue_calls == ["42"]
    text, _ = callback.message.edits[0]
    assert text.startswith(VPN_REISSUE_DONE_BANNER)
    assert "https://vpn.example/subscriptions/new-token/" in text
    assert "https://vpn.example/subscriptions/result-token/" not in text


async def test_vpn_reissue_api_error_preserves_confirmation():
    callback = FakeCallback(chat_id=42, user_id=42, data="vpn_reissue_confirm")
    error = APIError(
        "42", message="🔒 Пожалуйста, подождите 5 минут с последнего обновления."
    )
    vpn = FakeVPN(
        menu=VPNMenu(
            status="active",
            expired_at="2026-08-31T12:00:00+00:00",
            subscription_url="https://vpn.example/subscriptions/active/",
        ),
        reissue_error=error,
    )

    with pytest.raises(APIError) as exc_info:
        await process_vpn_reissue_confirm(callback, _deps_with_vpn(vpn=vpn))

    assert exc_info.value is error
    assert vpn.events == ["reissue"]
    assert callback.message.edits == []


async def test_vpn_stars_invoice_uses_distinct_payload_and_vpn_product(monkeypatch):
    fake_bot = FakeBot()
    monkeypatch.setattr("src.handlers.vpn.bot", fake_bot)
    stars = StarsInvoice(
        title="VPN на месяц",
        description="VPN-подписка",
        prices=[LabeledPrice(label="VPN на месяц", amount=149)],
        rub_amount="149.00",
        payment_methods=("stars", "crypto_pay"),
        priority_payment_methods=(),
    )

    await process_vpn_pay_stars(
        FakeCallback(chat_id=42),
        _deps_with_vpn(
            vpn=FakeVPN(
                menu=VPNMenu(status="none", expired_at=None, subscription_url=None)
            ),
            payments=FakePayments(stars=stars),
        ),
    )

    invoice = fake_bot.invoices[0]
    assert invoice["payload"] == "vpn_stars"
    assert invoice["currency"] == "XTR"
    assert invoice["prices"][0].amount == 149
