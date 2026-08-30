from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram.types import LabeledPrice
from src.domains.links import MyServers
from src.domains.payments import (
    ActivatedGiftCertificate,
    ConfirmedPurchase,
    CryptoInvoice,
    GiftCertificate,
    HistoricalPurchaseReplay,
    StarsInvoice,
)
from src.domains.vpn import VPNMenu, VPNPurchase
from src.exceptions import (
    APIError,
)
from src.handlers import payments as payments_module
from src.handlers import vpn as vpn_module
from src.handlers.payments import (
    process_boost_paid,
    process_gift_certificate,
    process_gift_certificate_activation,
    process_gift_crypto,
    process_gift_stars,
    process_pay_crypto,
    process_pay_stars,
    process_pre_checkout_query,
    process_successful_payment,
)
from src.handlers.vpn import (
    process_vpn,
    process_vpn_pay_crypto,
)
from src.messages import (
    CRYPTO_INVOICE_ERROR_TEXT,
    PRIVACY_URL,
    SUPPORT_URL,
    TERMS_URL,
)

from src import keyboards
from src import messages as messages_module
from tests.fakes import FakeBot, FakeCallback, FakeMessage, make_deps
from tests.handler_support import (
    APPROVED_GIFT_PAYMENT_TEXT,
    APPROVED_MTPROXY_PAYMENT_TEXT,
    APPROVED_VPN_PAYMENT_TEXT,
    FakePayments,
    FakeVPN,
    _deps_with_vpn,
    apple_loyalty,
)


async def test_payment_screen_includes_legal_links():
    callback = FakeCallback(chat_id=42)
    payments = FakePayments(
        stars=StarsInvoice(
            title="Месяц",
            description="прокси",
            prices=[LabeledPrice(label="Месяц", amount=237)],
            rub_amount="99.00",
            payment_methods=("stars", "crypto_pay"),
            priority_payment_methods=(),
        )
    )

    await process_boost_paid(callback, make_deps(payments=payments))

    text, markup = callback.message.edits[0]
    assert text == APPROVED_MTPROXY_PAYMENT_TEXT
    assert TERMS_URL in text
    assert PRIVACY_URL in text
    assert [
        [(button.text, button.callback_data) for button in row]
        for row in markup.inline_keyboard
    ] == [
        [("⭐ Telegram Stars — 237 ★", "pay_stars")],
        [("💎 Crypto Pay", "pay_crypto")],
        [("🔙 Назад", "show_mtproxy_menu")],
    ]


@pytest.mark.parametrize(
    ("builder", "kwargs", "expected_callbacks"),
    [
        (
            keyboards.payment_methods,
            {
                "stars_price": 237,
                "rub_amount": "99.00",
                "payment_methods": ("platega_sbp", "stars", "crypto_pay"),
                "priority_payment_methods": ("platega_sbp",),
            },
            [
                "pay_platega_sbp",
                "pay_stars",
                "pay_crypto",
                "show_mtproxy_menu",
            ],
        ),
        (
            keyboards.vpn_payment_methods,
            {
                "stars_price": 149,
                "rub_amount": "149.00",
                "payment_methods": ("platega_sbp", "stars", "crypto_pay"),
                "priority_payment_methods": ("platega_sbp",),
            },
            [
                "vpn_pay_platega_sbp",
                "vpn_pay_stars",
                "vpn_pay_crypto",
                "show_vpn_menu",
            ],
        ),
        (
            keyboards.gift_certificate_payment_methods,
            {
                "stars_price": 237,
                "rub_amount": "99.00",
                "payment_methods": ("platega_sbp", "stars", "crypto_pay"),
                "priority_payment_methods": ("platega_sbp",),
            },
            [
                "gift_platega_sbp",
                "gift_stars",
                "gift_crypto",
                "show_mtproxy_menu",
            ],
        ),
    ],
)
def test_sbp_first_stars_second_crypto_third(
    builder, kwargs, expected_callbacks
) -> None:
    markup = builder(**kwargs)

    assert [
        row[0].callback_data for row in markup.inline_keyboard
    ] == expected_callbacks
    assert markup.inline_keyboard[0][0].text.startswith("⚡ СБП — ")
    assert markup.inline_keyboard[0][0].style == "primary"
    assert markup.inline_keyboard[1][0].text.startswith("⭐ Telegram Stars")
    assert markup.inline_keyboard[2][0].text == "💎 Crypto Pay"


@pytest.mark.parametrize(
    ("builder", "kwargs", "back_callback"),
    [
        (
            keyboards.payment_methods,
            {
                "stars_price": 237,
                "rub_amount": "99.00",
                "payment_methods": ("unknown",),
                "priority_payment_methods": (),
            },
            "show_mtproxy_menu",
        ),
        (
            keyboards.vpn_payment_methods,
            {
                "stars_price": 149,
                "rub_amount": "149.00",
                "payment_methods": ("unknown",),
                "priority_payment_methods": (),
            },
            "show_vpn_menu",
        ),
        (
            keyboards.gift_certificate_payment_methods,
            {
                "stars_price": 237,
                "rub_amount": "99.00",
                "payment_methods": ("unknown",),
                "priority_payment_methods": (),
            },
            "show_mtproxy_menu",
        ),
    ],
)
def test_unknown_payment_method_keeps_only_back(builder, kwargs, back_callback) -> None:
    markup = builder(**kwargs)

    assert [row[0].callback_data for row in markup.inline_keyboard] == [back_callback]


def test_root_menu_links_to_common_destinations():
    markup = keyboards.product_menu()

    urls = [btn.url for row in markup.inline_keyboard for btn in row if btn.url]
    assert SUPPORT_URL == "https://t.me/mtprotokeys_support"
    assert "https://t.me/mtprotokeys_support" in urls
    assert "https://t.me/mtproto_keys" in urls
    assert set(urls) == {
        SUPPORT_URL,
        "https://t.me/mtproto_keys",
        TERMS_URL,
        PRIVACY_URL,
    }


def test_info_keyboard_returns_only_to_mtproxy():
    markup = keyboards.info()

    assert [
        [(button.text, button.callback_data, button.url) for button in row]
        for row in markup.inline_keyboard
    ] == [[("🔙 Назад", "show_mtproxy_menu", None)]]


def test_mtproxy_child_navigation_matches_parent_contract(
    servers: MyServers,
):
    markups = {
        "key_generated": keyboards.key_generated(),
        "my_servers": keyboards.my_servers(servers.servers),
        "info": keyboards.info(),
        "payment_methods": keyboards.payment_methods(
            stars_price=237,
            rub_amount="99.00",
            payment_methods=("stars", "crypto_pay"),
            priority_payment_methods=(),
        ),
        "gift_certificate": keyboards.gift_certificate_payment_methods(
            stars_price=237,
            rub_amount="99.00",
            payment_methods=("stars", "crypto_pay"),
            priority_payment_methods=(),
        ),
    }

    assert {
        name: markup.inline_keyboard[-1][0].callback_data
        for name, markup in markups.items()
    } == {name: "show_mtproxy_menu" for name in markups}
    assert (
        keyboards.confirm_reissue().inline_keyboard[-1][0].callback_data == "my_servers"
    )
    assert [
        button.callback_data
        for row in keyboards.key_generated().inline_keyboard
        for button in row
    ] == ["my_servers", "show_mtproxy_menu"]
    assert [
        (button.text, button.callback_data, button.url)
        for row in keyboards.info().inline_keyboard
        for button in row
    ] == [("🔙 Назад", "show_mtproxy_menu", None)]


SCREEN_CASES = {
    "mtproxy": (
        process_boost_paid,
        APPROVED_MTPROXY_PAYMENT_TEXT,
        {
            "platega_sbp": ("⚡ СБП — 99 ₽", "pay_platega_sbp"),
            "stars": ("⭐ Telegram Stars — 237 ★", "pay_stars"),
            "crypto_pay": ("💎 Crypto Pay", "pay_crypto"),
        },
        ("🔙 Назад", "show_mtproxy_menu"),
    ),
    "vpn": (
        process_vpn,
        APPROVED_VPN_PAYMENT_TEXT,
        {
            "platega_sbp": ("⚡ СБП — 99 ₽", "vpn_pay_platega_sbp"),
            "stars": ("⭐ Telegram Stars — 237 ★", "vpn_pay_stars"),
            "crypto_pay": ("💎 Crypto Pay", "vpn_pay_crypto"),
        },
        ("🔙 Назад", "show_vpn_menu"),
    ),
    "gift": (
        process_gift_certificate,
        APPROVED_GIFT_PAYMENT_TEXT,
        {
            "platega_sbp": ("⚡ СБП — 99 ₽", "gift_platega_sbp"),
            "stars": ("⭐ Telegram Stars — 237 ★", "gift_stars"),
            "crypto_pay": ("💎 Crypto Pay", "gift_crypto"),
        },
        ("🔙 Назад", "show_mtproxy_menu"),
    ),
}


@pytest.mark.parametrize("screen", tuple(SCREEN_CASES))
@pytest.mark.parametrize(
    ("methods", "priority_methods", "expected_method_styles"),
    (
        (
            ("platega_sbp", "stars", "crypto_pay"),
            ("stars",),
            (
                ("platega_sbp", None),
                ("stars", "primary"),
                ("crypto_pay", None),
            ),
        ),
        (
            ("platega_sbp", "stars", "crypto_pay"),
            ("platega_sbp", "crypto_pay"),
            (
                ("platega_sbp", "primary"),
                ("stars", None),
                ("crypto_pay", "primary"),
            ),
        ),
        (
            ("platega_sbp", "stars", "crypto_pay"),
            (),
            (
                ("platega_sbp", None),
                ("stars", None),
                ("crypto_pay", None),
            ),
        ),
        (
            ("platega_sbp", "stars"),
            (),
            (("platega_sbp", None), ("stars", None)),
        ),
        (
            ("platega_sbp", "crypto_pay"),
            (),
            (("platega_sbp", None), ("crypto_pay", None)),
        ),
        (("platega_sbp",), (), (("platega_sbp", None),)),
        (
            ("stars", "crypto_pay"),
            (),
            (("stars", None), ("crypto_pay", None)),
        ),
        (("stars",), (), (("stars", None),)),
        (("crypto_pay",), (), (("crypto_pay", None),)),
        ((), (), ()),
    ),
)
async def test_payment_method_screen_matrix(
    screen, methods, priority_methods, expected_method_styles
) -> None:
    handler, normal_text, button_by_method, back_button = SCREEN_CASES[screen]
    invoice = StarsInvoice(
        title="Товар",
        description="Описание",
        prices=[LabeledPrice(label="Товар", amount=237)],
        rub_amount="99.00",
        payment_methods=methods,
        priority_payment_methods=priority_methods,
    )
    payments = FakePayments(stars=invoice)
    callback = FakeCallback(chat_id=42, user_id=42)
    if screen == "vpn":
        deps = _deps_with_vpn(
            vpn=FakeVPN(
                menu=VPNMenu(
                    status="none",
                    expired_at=None,
                    subscription_url=None,
                )
            ),
            payments=payments,
        )
    else:
        deps = make_deps(payments=payments)

    await handler(callback, deps)

    text, markup = callback.message.edits[0]
    expected_rows = [
        [(*button_by_method[code], style)] for code, style in expected_method_styles
    ]
    expected_rows.append([(*back_button, None)])
    actual_rows = [
        [(button.text, button.callback_data, button.style) for button in row]
        for row in markup.inline_keyboard
    ]
    assert actual_rows == expected_rows
    assert text == (normal_text if methods else "Оплата временно недоступна")
    assert payments.stars_invoice_calls == (0 if screen == "vpn" else 1)
    assert payments.vpn_stars_invoice_calls == (1 if screen == "vpn" else 0)


@pytest.mark.parametrize(
    ("builder", "kwargs"),
    [
        (
            keyboards.payment_methods,
            {
                "stars_price": 237,
                "rub_amount": "99.50",
                "payment_methods": ("platega_sbp",),
                "priority_payment_methods": ("platega_sbp",),
            },
        ),
        (
            keyboards.vpn_payment_methods,
            {
                "stars_price": 149,
                "rub_amount": "99.50",
                "payment_methods": ("platega_sbp",),
                "priority_payment_methods": ("platega_sbp",),
            },
        ),
        (
            keyboards.gift_certificate_payment_methods,
            {
                "stars_price": 237,
                "rub_amount": "99.50",
                "payment_methods": ("platega_sbp",),
                "priority_payment_methods": ("platega_sbp",),
            },
        ),
    ],
)
def test_sbp_fractional_rub_label_uses_comma_and_primary_style(builder, kwargs) -> None:
    button = builder(**kwargs).inline_keyboard[0][0]

    assert button.text == "⚡ СБП — 99,50 ₽"
    assert button.style == "primary"


async def test_pay_stars_sends_xtr_invoice(monkeypatch):
    fake_bot = FakeBot()
    monkeypatch.setattr(payments_module, "bot", fake_bot)
    stars = StarsInvoice(
        title="Месяц",
        description="прокси",
        prices=[LabeledPrice(label="Месяц", amount=99)],
        rub_amount="99.00",
        payment_methods=("stars", "crypto_pay"),
        priority_payment_methods=(),
    )
    callback = FakeCallback(chat_id=42)

    await process_pay_stars(callback, make_deps(payments=FakePayments(stars=stars)))

    invoice = fake_bot.invoices[0]
    assert invoice["currency"] == "XTR"
    assert invoice["prices"][0].amount == 99


async def test_gift_certificate_screen_shows_payment_options():
    callback = FakeCallback(chat_id=42)
    payments = FakePayments(
        stars=StarsInvoice(
            title="Месяц",
            description="прокси",
            prices=[LabeledPrice(label="Месяц", amount=237)],
            rub_amount="99.00",
            payment_methods=("stars", "crypto_pay"),
            priority_payment_methods=(),
        )
    )

    await process_gift_certificate(callback, make_deps(payments=payments))

    text, markup = callback.message.edits[0]
    assert text == APPROVED_GIFT_PAYMENT_TEXT
    assert [
        [(button.text, button.callback_data) for button in row]
        for row in markup.inline_keyboard
    ] == [
        [("⭐ Telegram Stars — 237 ★", "gift_stars")],
        [("💎 Crypto Pay", "gift_crypto")],
        [("🔙 Назад", "show_mtproxy_menu")],
    ]


async def test_gift_stars_invoice_uses_gift_payload(monkeypatch):
    fake_bot = FakeBot()
    monkeypatch.setattr(payments_module, "bot", fake_bot)
    stars = StarsInvoice(
        title="Месяц",
        description="прокси",
        prices=[LabeledPrice(label="Месяц", amount=99)],
        rub_amount="99.00",
        payment_methods=("stars", "crypto_pay"),
        priority_payment_methods=(),
    )
    callback = FakeCallback(chat_id=42)

    await process_gift_stars(callback, make_deps(payments=FakePayments(stars=stars)))

    invoice = fake_bot.invoices[0]
    assert invoice["payload"] == "gift_certificate_stars"
    assert invoice["currency"] == "XTR"
    assert invoice["prices"][0].amount == 99


@pytest.mark.parametrize(
    ("handler", "purchase_kind", "back_callback"),
    [
        (process_pay_crypto, "subscription", "show_mtproxy_menu"),
        (process_vpn_pay_crypto, "vpn_subscription", "show_vpn_menu"),
        (process_gift_crypto, "gift_certificate", "show_mtproxy_menu"),
    ],
)
async def test_crypto_callback_uses_kind_and_shows_url(
    monkeypatch,
    handler,
    purchase_kind: str,
    back_callback: str,
) -> None:
    fake_bot = FakeBot()
    monkeypatch.setattr(payments_module, "bot", fake_bot)
    monkeypatch.setattr(vpn_module, "bot", fake_bot)
    payments = FakePayments(
        crypto=CryptoInvoice(
            invoice_url="https://t.me/CryptoBot?start=x",
            rub_amount="99.00",
            expires_at="2026-08-02T12:30:00.123456Z",
            reused=False,
        )
    )
    callback = FakeCallback(user_id=42)

    await handler(callback, make_deps(payments=payments))

    assert callback.answers == [((), {})]
    assert payments.crypto_calls == [(42, purchase_kind)]
    assert fake_bot.invoices == []
    text, markup = callback.message.edits[0]
    assert "99 ₽" in text
    assert "02.08.2026, 15:30 МСК" in text
    assert "99.00" not in text
    assert "2026-08-02T12:30:00.123456Z" not in text
    assert text.rstrip().endswith("Нажми кнопку ниже, чтобы открыть CryptoBot.")
    assert markup.inline_keyboard[0][0].url == "https://t.me/CryptoBot?start=x"
    assert markup.inline_keyboard[1][0].callback_data == back_callback


async def test_crypto_error_keeps_current_keyboard_retryable() -> None:
    payments = FakePayments(crypto_error=APIError(42, message="safe"))
    callback = FakeCallback(user_id=42)

    await process_pay_crypto(callback, make_deps(payments=payments))

    assert callback.answers == [((), {})]
    assert payments.crypto_calls == [(42, "subscription")]
    assert callback.message.edits == []
    assert callback.message.answers == [(CRYPTO_INVOICE_ERROR_TEXT, None)]
    assert "Попробуй нажать кнопку ещё раз." in CRYPTO_INVOICE_ERROR_TEXT


@pytest.mark.parametrize(
    ("handler_module", "handler_name", "purchase_kind", "back_callback"),
    [
        (
            payments_module,
            "process_pay_platega_sbp",
            "subscription",
            "show_mtproxy_menu",
        ),
        (
            vpn_module,
            "process_vpn_pay_platega_sbp",
            "vpn_subscription",
            "show_vpn_menu",
        ),
        (
            payments_module,
            "process_gift_platega_sbp",
            "gift_certificate",
            "show_mtproxy_menu",
        ),
    ],
)
async def test_platega_callback_uses_kind_and_shows_url_with_correct_back_target(
    handler_module,
    handler_name: str,
    purchase_kind: str,
    back_callback: str,
) -> None:
    payments = FakePayments(
        platega=SimpleNamespace(
            payment_url="https://pay.example/invoice/opaque",
            rub_amount="99.50",
            expires_at="2026-08-08T12:15:00Z",
            reused=False,
        )
    )
    callback = FakeCallback(user_id=42, username=None)

    await getattr(handler_module, handler_name)(
        callback,
        make_deps(payments=payments),
    )

    assert callback.answers == [((), {})]
    assert payments.platega_calls == [(42, purchase_kind)]
    text, markup = callback.message.edits[0]
    assert "99,50 ₽" in text
    assert "99.50" not in text
    assert "Срок действия счета: 15 минут" in text
    assert "2026-08-08T12:15:00Z" not in text
    assert "Возврат в бот не подтверждает оплату" not in text
    assert "Результат будет выдан автоматически после подтверждения платежа." in text
    assert text.rstrip().endswith("Нажми кнопку ниже, чтобы перейти к оплате.")
    assert markup.inline_keyboard[0][0].text == "Оплатить через СБП"
    assert markup.inline_keyboard[0][0].url == ("https://pay.example/invoice/opaque")
    assert markup.inline_keyboard[1][0].callback_data == back_callback


@pytest.mark.parametrize(
    ("handler_module", "handler_name", "purchase_kind"),
    [
        (payments_module, "process_pay_platega_sbp", "subscription"),
        (vpn_module, "process_vpn_pay_platega_sbp", "vpn_subscription"),
        (
            payments_module,
            "process_gift_platega_sbp",
            "gift_certificate",
        ),
    ],
)
async def test_platega_backend_error_shows_retryable_error_without_editing_screen(
    handler_module,
    handler_name: str,
    purchase_kind: str,
) -> None:
    payments = FakePayments(platega_error=APIError(42, message="safe"))
    callback = FakeCallback(user_id=42)

    await getattr(handler_module, handler_name)(
        callback,
        make_deps(payments=payments),
    )

    assert callback.answers == [((), {})]
    assert payments.platega_calls == [(42, purchase_kind)]
    assert callback.message.edits == []
    assert callback.message.answers == [
        (messages_module.PLATEGA_INVOICE_ERROR_TEXT, None)
    ]
    assert "Попробуй нажать кнопку ещё раз." in (
        messages_module.PLATEGA_INVOICE_ERROR_TEXT
    )


async def test_successful_payment_uses_stars_provider_and_charge_id():
    payments = FakePayments()
    message = FakeMessage(user_id=42)
    message.successful_payment = SimpleNamespace(
        currency="XTR",
        telegram_payment_charge_id="ch_stars",
        provider_payment_charge_id="ch_card",
    )

    await process_successful_payment(message, make_deps(payments=payments))

    assert payments.confirmed == [(42, "ch_stars", "stars")]


async def test_successful_mtproxy_payment_sends_one_combined_saved_result():
    outcome = apple_loyalty()
    payments = FakePayments(
        purchase=ConfirmedPurchase(
            expired_date="2026-09-18",
            loyalty=outcome,
        )
    )
    message = FakeMessage(user_id=42)
    message.successful_payment = SimpleNamespace(
        currency="XTR",
        invoice_payload="payment_stars",
        telegram_payment_charge_id="subscription_charge",
        provider_payment_charge_id="unused",
    )

    await process_successful_payment(message, make_deps(payments=payments))

    assert payments.confirmed == [(42, "subscription_charge", "stars")]
    assert len(message.answers) == 1
    text, markup = message.answers[0]
    assert "Подписка активна до: <b>18.09.2026</b>" in text
    assert "Начислено: <b>5 🍏</b>" in text
    assert "Ставка: <b>5%</b>" in text
    assert "Баланс: <b>20 🍏</b>" in text
    assert "Уровень: <b>Садовник</b>" in text
    assert "🎉 Новый уровень: <b>Садовник</b>" in text
    assert "Кэшбэк следующей покупки: <b>10%</b>" in text
    assert text.index("🍏 <b>Кэшбэк</b>") < text.index(
        "👇 Нажми «Мои серверы», чтобы подключиться ко всем серверам"
    )
    assert text.rstrip().endswith(
        "👇 Нажми «Мои серверы», чтобы подключиться ко всем серверам"
    )
    assert [
        button.callback_data for row in markup.inline_keyboard for button in row
    ] == [
        "my_servers",
        "show_mtproxy_menu",
    ]


async def test_successful_gift_payment_keeps_code_and_adds_same_loyalty_result():
    payments = FakePayments(
        gift=GiftCertificate(
            code="KEY-ABCD-1234",
            loyalty=apple_loyalty(),
        )
    )
    message = FakeMessage(user_id=42)
    message.successful_payment = SimpleNamespace(
        currency="XTR",
        invoice_payload="gift_certificate_stars",
        telegram_payment_charge_id="gift_charge",
        provider_payment_charge_id="unused",
    )

    await process_successful_payment(message, make_deps(payments=payments))

    assert payments.gift_confirmed == [(42, "gift_charge", "stars")]
    assert len(message.answers) == 1
    text, _ = message.answers[0]
    assert "<code>KEY-ABCD-1234</code>" in text
    assert "Начислено: <b>5 🍏</b>" in text
    assert "Ставка: <b>5%</b>" in text
    assert "Баланс: <b>20 🍏</b>" in text
    assert "Уровень: <b>Садовник</b>" in text
    assert "Кэшбэк следующей покупки: <b>10%</b>" in text


@pytest.mark.parametrize(
    ("invoice_payload", "purchase_kind"),
    [
        ("payment_stars", "subscription"),
        ("gift_certificate_stars", "gift"),
    ],
)
async def test_historical_sync_purchase_replay_is_silent(
    invoice_payload: str,
    purchase_kind: str,
):
    replay = HistoricalPurchaseReplay()
    payments = FakePayments(
        purchase=replay if purchase_kind == "subscription" else None,
        gift=replay if purchase_kind == "gift" else None,
    )
    message = FakeMessage(user_id=42)
    message.successful_payment = SimpleNamespace(
        currency="XTR",
        invoice_payload=invoice_payload,
        telegram_payment_charge_id="historical_charge",
        provider_payment_charge_id="unused",
    )

    await process_successful_payment(message, make_deps(payments=payments))

    assert message.answers == []


@pytest.mark.parametrize("purchase_kind", ["subscription", "gift"])
async def test_post_launch_duplicate_keeps_ordinary_combined_message(
    purchase_kind: str,
):
    outcome = apple_loyalty(
        apples_earned=15,
        rate_percent=15,
        balance=52,
        eligible_purchase_count=8,
        level="Мастер сада",
        level_up=False,
        next_purchase_rate_percent=15,
    )
    payments = FakePayments(
        purchase=ConfirmedPurchase(
            expired_date="2026-10-18",
            loyalty=outcome,
        ),
        gift=GiftCertificate(
            code="KEY-DUPL-0001",
            loyalty=outcome,
        ),
    )
    payload = (
        "payment_stars" if purchase_kind == "subscription" else "gift_certificate_stars"
    )
    messages = []

    for _ in range(2):
        message = FakeMessage(user_id=42)
        message.successful_payment = SimpleNamespace(
            currency="XTR",
            invoice_payload=payload,
            telegram_payment_charge_id="same_post_launch_charge",
            provider_payment_charge_id="unused",
        )
        await process_successful_payment(message, make_deps(payments=payments))
        messages.append(message.answers[0][0])

    assert messages[0] == messages[1]
    assert "Начислено: <b>15 🍏</b>" in messages[1]
    assert "Баланс: <b>52 🍏</b>" in messages[1]
    assert "🎉 Новый уровень" not in messages[1]


async def test_successful_gift_payment_returns_code_to_forward():
    payments = FakePayments(
        gift=GiftCertificate(
            code="KEY-ABCD-1234",
            loyalty=apple_loyalty(),
        )
    )
    message = FakeMessage(user_id=42)
    message.successful_payment = SimpleNamespace(
        currency="XTR",
        invoice_payload="gift_certificate_stars",
        telegram_payment_charge_id="gift_ch_stars",
        provider_payment_charge_id="unused",
    )

    await process_successful_payment(message, make_deps(payments=payments))

    assert payments.gift_confirmed == [(42, "gift_ch_stars", "stars")]
    text, _ = message.answers[0]
    assert "KEY-ABCD-1234" in text
    assert "перешл" in text.lower()


async def test_successful_regular_payment_ignores_gift_confirmation():
    payments = FakePayments()
    message = FakeMessage(user_id=42)
    message.successful_payment = SimpleNamespace(
        currency="XTR",
        invoice_payload="payment_stars",
        telegram_payment_charge_id="ch_stars",
        provider_payment_charge_id="ch_card",
    )

    await process_successful_payment(message, make_deps(payments=payments))

    assert payments.confirmed == [(42, "ch_stars", "stars")]
    assert payments.gift_confirmed == []


@pytest.mark.parametrize(
    ("currency", "invoice_payload", "expected_charge_id", "expected_provider"),
    [
        ("XTR", "vpn_stars", "vpn_ch_stars", "stars"),
    ],
)
async def test_successful_vpn_payment_shows_approved_parent_actions(
    currency, invoice_payload, expected_charge_id, expected_provider
):
    payments = FakePayments()
    vpn = FakeVPN(
        menu=VPNMenu(status="none", expired_at=None, subscription_url=None),
        purchase=VPNPurchase(
            expired_at="2026-08-31T22:30:00+00:00",
            subscription_url="https://vpn.example/subscriptions/token/",
        ),
    )
    message = FakeMessage(user_id=42)
    message.successful_payment = SimpleNamespace(
        currency=currency,
        invoice_payload=invoice_payload,
        telegram_payment_charge_id="vpn_ch_stars",
        provider_payment_charge_id="vpn_ch_card",
    )

    await process_successful_payment(
        message, _deps_with_vpn(vpn=vpn, payments=payments)
    )

    assert vpn.purchase_calls == [(42, expected_charge_id, expected_provider)]
    assert payments.confirmed == []
    text, markup = message.answers[0]
    assert "01.09.2026" in text
    assert "22:30" not in text
    assert "МСК" not in text
    assert "2026-08-31T22:30:00+00:00" not in text
    assert "https://vpn.example/subscriptions/token/" in text
    assert "Android" in text
    assert "iOS" in text
    assert "Windows" in text
    assert "macOS" in text
    assert markup is not None
    assert [
        [(button.text, button.callback_data, button.style) for button in row]
        for row in markup.inline_keyboard
    ] == [
        [("🔑 Моя подписка", "vpn_subscription", "primary")],
        [("🔙 Назад в VPN", "show_vpn_menu", None)],
    ]


async def test_gift_certificate_code_message_activates_certificate():
    payments = FakePayments(
        activation=ActivatedGiftCertificate(expired_date="08.08.26")
    )
    message = FakeMessage(user_id=42, text="KEY-ABCD-1234")

    await process_gift_certificate_activation(message, make_deps(payments=payments))

    assert payments.activated == [(42, "KEY-ABCD-1234")]
    text, _ = message.answers[0]
    assert "08.08.2026" in text
    assert "08.08.26" not in text


async def test_gift_certificate_activation_failure_uses_support_contact():
    payments = FakePayments(activation_error=RuntimeError("boom"))
    message = FakeMessage(user_id=42, text="KEY-ABCD-1234")

    await process_gift_certificate_activation(message, make_deps(payments=payments))

    text, _ = message.answers[0]
    assert "@mtprotokeys_support" in text
    assert "Напиши в поддержку" in text
    assert "@mtproto_keys" not in text


async def test_successful_payment_warns_user_on_failure():
    payments = FakePayments(confirm_error=RuntimeError("boom"))
    message = FakeMessage(user_id=42)
    message.successful_payment = SimpleNamespace(
        currency="XTR",
        telegram_payment_charge_id="ch",
        provider_payment_charge_id="ch",
    )

    await process_successful_payment(message, make_deps(payments=payments))

    text, _ = message.answers[0]
    assert "обратись в поддержку" in text
    assert "@mtprotokeys_support" in text
    assert "@mtproto_keys" not in text


@pytest.mark.parametrize(
    ("currency", "expected_ok"),
    [("XTR", True), ("RUB", False)],
)
async def test_pre_checkout_query_accepts_only_stars(
    monkeypatch,
    currency,
    expected_ok,
):
    fake_bot = FakeBot()
    monkeypatch.setattr(payments_module, "bot", fake_bot)
    pre_checkout = SimpleNamespace(id="q1", currency=currency)

    await process_pre_checkout_query(pre_checkout)

    args, kwargs = fake_bot.pre_checkout[0]
    assert args[0] == "q1"
    assert kwargs["ok"] is expected_ok
    if expected_ok:
        assert "error_message" not in kwargs
    else:
        assert kwargs["error_message"] == "Этот способ оплаты больше не поддерживается"
