from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from aiogram.types import LabeledPrice

from src import keyboards, messages as messages_module
from src.exceptions import (
    APIError,
    VPNReissueRequiresRenewal,
    VPNSubscriptionDoesNotExist,
)
from src.handlers import payments as payments_module
from src.handlers import vpn as vpn_module
from src.handlers.free_trial import process_boost_free
from src.handlers.links import process_my_servers, update_link, update_link_confirm
from src.handlers.payments import (
    process_gift_certificate,
    process_gift_certificate_activation,
    process_gift_crypto,
    process_gift_stars,
    process_boost_paid,
    process_pay_crypto,
    process_pay_stars,
    process_pre_checkout_query,
    process_successful_payment,
)
from src.handlers.vpn import (
    process_vpn,
    process_vpn_menu,
    process_vpn_pay_crypto,
    process_vpn_pay_stars,
    process_vpn_reissue,
    process_vpn_reissue_confirm,
    process_vpn_subscription,
)
from src.handlers.referrals import process_referral, process_referral_link
from src.handlers.start import (
    cmd_start,
    cmd_start_inline,
    process_info,
    process_legal_consent,
    process_mtproxy_menu,
)
from src.messages import (
    CRYPTO_INVOICE_ERROR_TEXT,
    KEY_GENERATED_TEXT,
    PRIVACY_URL,
    PRODUCT_MENU_TEXT,
    SITE_URL,
    SUPPORT_URL,
    TERMS_URL,
    VPN_REISSUE_CONFIRM_TEXT,
    VPN_REISSUE_DONE_BANNER,
    VPN_PRODUCT_MENU_TEXT,
    WELCOME_TEXT_MONTH,
    WELCOME_TEXT_NOT_FREE,
)
from src.domains.free_trial import FreeTrialKey
from src.domains.links import MyServers, ReissuedKey, ServerItem
from src.domains.payments import (
    ActivatedGiftCertificate,
    ApplePurchaseOutcome,
    AppleRedemptionPreview,
    AppleRedemptionResult,
    AppleStatus,
    ConfirmedPurchase,
    CryptoInvoice,
    GiftCertificate,
    HistoricalPurchaseReplay,
    StarsInvoice,
)
from src.domains.referrals import ReferralCabinet, ReferralRewardKey
from src.domains.vpn import VPNMenu, VPNPurchase, VPNReissue
from tests.fakes import FakeBot, FakeCallback, FakeMessage, make_deps


APPROVED_MTPROXY_PAYMENT_TEXT = """💳 <b>Оплата подписки</b>

⚡ <b>Продукт:</b> MTProxy
📅 <b>Период:</b> 30 дней

После оплаты новый ключ будет выдан автоматически. Если у вас уже есть активный ключ, подписка продлится на 30 дней.

<i>Оплачивая подписку, вы принимаете <a href="https://mtprotokeys.com/terms">Условия использования</a> и <a href="https://mtprotokeys.com/privacy">Политику конфиденциальности</a>.</i>

👇 <b>Выберите способ оплаты:</b>"""

APPROVED_VPN_PAYMENT_TEXT = """💳 <b>Оплата подписки</b>

🔐 <b>Продукт:</b> VPN
📅 <b>Период:</b> 30 дней

После оплаты VPN-подписка будет активирована автоматически. При продлении ваша постоянная subscription-ссылка не изменится.

<i>Оплачивая подписку, вы принимаете <a href="https://mtprotokeys.com/terms">Условия использования</a> и <a href="https://mtprotokeys.com/privacy">Политику конфиденциальности</a>.</i>

👇 <b>Выберите способ оплаты:</b>"""

APPROVED_GIFT_PAYMENT_TEXT = """💳 <b>Оплата подарка</b>

🎁 <b>Продукт:</b> сертификат MTProxy
📅 <b>Период:</b> 30 дней

После оплаты вы получите одноразовый код, который можно переслать другому человеку. Код создаст новый ключ или продлит действующий на 30 дней.

<i>Оплачивая сертификат, вы принимаете <a href="https://mtprotokeys.com/terms">Условия использования</a> и <a href="https://mtprotokeys.com/privacy">Политику конфиденциальности</a>.</i>

👇 <b>Выберите способ оплаты:</b>"""


def apple_loyalty(
    *,
    apples_earned: int = 5,
    rate_percent: int = 5,
    balance: int = 20,
    eligible_purchase_count: int = 4,
    level: str = "Садовник",
    level_up: bool = True,
    next_purchase_rate_percent: int = 10,
) -> ApplePurchaseOutcome:
    return ApplePurchaseOutcome(
        apples_earned=apples_earned,
        rate_percent=rate_percent,
        balance=balance,
        eligible_purchase_count=eligible_purchase_count,
        level=level,
        level_up=level_up,
        next_purchase_rate_percent=next_purchase_rate_percent,
    )


# --- domain fakes -----------------------------------------------------------


class FakeFreeTrial:
    def __init__(
        self,
        *,
        check="MONTH",
        key=None,
        consent=True,
        accept_result=True,
    ) -> None:
        self._check = check
        self._key = key or FreeTrialKey(expired_date="2026-07-14")
        self._consent = consent
        self._accept_result = accept_result
        self.checked: list[tuple] = []
        self.claimed: list[str] = []
        self.status_checked: list[str] = []
        self.accepted: list[tuple] = []

    async def get_consent_status(self, *, telegram_id):
        self.status_checked.append(telegram_id)
        return self._consent

    async def accept_consent(
        self, *, telegram_id, telegram_username, invited_from_username=None
    ):
        self.accepted.append(
            (telegram_id, telegram_username, invited_from_username)
        )
        return self._accept_result

    async def check_availability(
        self, *, telegram_id, telegram_username, invited_from_username=None
    ):
        self.checked.append((telegram_id, telegram_username, invited_from_username))
        return self._check

    async def claim(self, *, telegram_id):
        self.claimed.append(telegram_id)
        return self._key


class FakeLinks:
    def __init__(self, *, servers, reissue=None) -> None:
        self._servers = servers
        self._reissue = reissue or ReissuedKey(expired_date="2026-07-14")
        self.get_calls: list[str] = []
        self.reissue_calls: list[str] = []

    async def get_my_servers(self, *, telegram_id):
        self.get_calls.append(telegram_id)
        return self._servers

    async def reissue(self, *, telegram_id):
        self.reissue_calls.append(telegram_id)
        return self._reissue


class FakeReferrals:
    def __init__(self, *, cabinet, reward=None) -> None:
        self._cabinet = cabinet
        self._reward = reward or ReferralRewardKey(
            expired_date="2026-06-28"
        )
        self.cabinet_calls: list[str] = []
        self.reward_calls: list[str] = []

    async def get_cabinet(self, *, telegram_id):
        self.cabinet_calls.append(telegram_id)
        return self._cabinet

    async def claim_reward(self, *, telegram_id):
        self.reward_calls.append(telegram_id)
        return self._reward


class FakePayments:
    def __init__(
        self,
        *,
        stars=None,
        purchase=None,
        gift=None,
        activation=None,
        confirm_error=None,
        activation_error=None,
        crypto=None,
        crypto_error=None,
        platega=None,
        platega_error=None,
        apple_status=None,
        apple_preview=None,
        apple_result=None,
        apple_preview_error=None,
        apple_confirm_error=None,
    ) -> None:
        self._stars = stars
        default_loyalty = ApplePurchaseOutcome(
            apples_earned=5,
            rate_percent=5,
            balance=5,
            eligible_purchase_count=1,
            level="Новичок",
            level_up=False,
            next_purchase_rate_percent=5,
        )
        self._purchase = purchase or ConfirmedPurchase(
            expired_date="2026-09-18",
            loyalty=default_loyalty,
        )
        self._gift = gift or GiftCertificate(
            code="KEY-ABCD-1234",
            loyalty=default_loyalty,
        )
        self._activation = activation or ActivatedGiftCertificate(
            expired_date="2026-08-08"
        )
        self._confirm_error = confirm_error
        self._activation_error = activation_error
        self._crypto = crypto
        self._crypto_error = crypto_error
        self._platega = platega
        self._platega_error = platega_error
        self._apple_status = apple_status
        self._apple_preview = apple_preview
        self._apple_result = apple_result
        self._apple_preview_error = apple_preview_error
        self._apple_confirm_error = apple_confirm_error
        self.confirmed: list[tuple] = []
        self.gift_confirmed: list[tuple] = []
        self.activated: list[tuple] = []
        self.stars_invoice_calls = 0
        self.vpn_stars_invoice_calls = 0
        self.crypto_calls: list[tuple] = []
        self.platega_calls: list[tuple] = []
        self.apple_status_calls: list[int] = []
        self.apple_preview_calls: list[tuple[int, str]] = []
        self.apple_confirm_calls: list[tuple[int, int]] = []

    async def get_stars_invoice(self):
        self.stars_invoice_calls += 1
        return self._stars

    async def get_vpn_stars_invoice(self):
        self.vpn_stars_invoice_calls += 1
        return self._stars

    async def confirm_purchase(self, *, telegram_id, charge_id, provider):
        self.confirmed.append((telegram_id, charge_id, provider))
        if self._confirm_error is not None:
            raise self._confirm_error
        return self._purchase

    async def confirm_gift_certificate_purchase(self, *, telegram_id, charge_id, provider):
        self.gift_confirmed.append((telegram_id, charge_id, provider))
        if self._confirm_error is not None:
            raise self._confirm_error
        return self._gift

    async def activate_gift_certificate(self, *, telegram_id, code):
        self.activated.append((telegram_id, code))
        if self._activation_error is not None:
            raise self._activation_error
        return self._activation

    async def create_crypto_invoice(self, *, telegram_id, purchase_kind):
        self.crypto_calls.append((telegram_id, purchase_kind))
        if self._crypto_error is not None:
            raise self._crypto_error
        return self._crypto

    async def create_platega_invoice(self, *, telegram_id, purchase_kind):
        self.platega_calls.append((telegram_id, purchase_kind))
        if self._platega_error is not None:
            raise self._platega_error
        return self._platega

    async def get_apple_status(self, *, telegram_id):
        self.apple_status_calls.append(telegram_id)
        return self._apple_status

    async def preview_apple_redemption(self, *, telegram_id, mode):
        self.apple_preview_calls.append((telegram_id, mode))
        if self._apple_preview_error is not None:
            raise self._apple_preview_error
        return self._apple_preview

    async def confirm_apple_redemption(self, *, telegram_id, confirmation_id):
        self.apple_confirm_calls.append((telegram_id, confirmation_id))
        if self._apple_confirm_error is not None:
            raise self._apple_confirm_error
        return self._apple_result


class FakeVPN:
    def __init__(
        self,
        *,
        menu: VPNMenu | list[VPNMenu],
        purchase: VPNPurchase | None = None,
        reissue: VPNReissue | None = None,
        reissue_error: APIError | None = None,
    ) -> None:
        self._menus = menu if isinstance(menu, list) else [menu]
        self._purchase = purchase or VPNPurchase(
            expired_at="2026-08-31T12:00:00+00:00",
            subscription_url="https://vpn.example/subscriptions/token/",
        )
        self._reissue = reissue or VPNReissue(
            expired_at="2026-08-31T12:00:00+00:00",
            subscription_url="https://vpn.example/subscriptions/reissued/",
        )
        self._reissue_error = reissue_error
        self.menu_calls: list[str] = []
        self.purchase_calls: list[tuple] = []
        self.reissue_calls: list[str] = []
        self.events: list[str] = []

    async def get_menu(self, *, telegram_id):
        self.menu_calls.append(telegram_id)
        self.events.append("menu")
        return self._menus.pop(0)

    async def confirm_purchase(self, *, telegram_id, charge_id, provider):
        self.purchase_calls.append((telegram_id, charge_id, provider))
        return self._purchase

    async def reissue(self, *, telegram_id):
        self.reissue_calls.append(telegram_id)
        self.events.append("reissue")
        if self._reissue_error is not None:
            raise self._reissue_error
        return self._reissue


def _deps_with_vpn(*, vpn: FakeVPN, payments: FakePayments | None = None):
    from src.dependencies import Dependencies

    if payments is None:
        payments = FakePayments(
            stars=StarsInvoice(
                title="VPN на месяц",
                description="VPN-подписка",
                prices=[LabeledPrice(label="VPN на месяц", amount=149)],
                rub_amount="149.00",
                payment_methods=("stars", "crypto_pay"),
                priority_payment_methods=(),
            ),
        )
    return Dependencies(
        free_trial=None,
        links=None,
        referrals=None,
        payments=payments,
        vpn=vpn,
    )


@pytest.fixture
def servers() -> MyServers:
    return MyServers(
        expired_date="2026-07-14",
        servers=[ServerItem(location="🇳🇱 Нидерланды", proxy_link="tg://proxy?a=1")],
    )


# --- start screen -----------------------------------------------------------


async def test_root_navigation_matches_approved_hierarchy():
    fake = FakeFreeTrial(check="MONTH")
    message = FakeMessage(text="/start", user_id=42, username="bob")

    await cmd_start(message, make_deps(free_trial=fake))

    assert fake.status_checked == ["42"]
    assert fake.checked == []
    text, markup = message.answers[0]
    assert text == PRODUCT_MENU_TEXT == (
        "👋 Добро пожаловать в MTProto Keys!\n\n"
        "MTProxy, VPN, бонусы и полезные ссылки — всё здесь.\n"
        "Выберите, что вас интересует:"
    )
    expected_rows = [
        [("⚡ MTProxy", "show_mtproxy_menu", None, "success")],
        [("🔐 VPN", "show_vpn_menu", None, "primary")],
        [("🤝 Реферальная программа", "referral", None, None)],
        [("💬 Написать в поддержку", None, SUPPORT_URL, None)],
        [("🌐 Наш сайт", None, SITE_URL, None)],
        [
            ("📜 Условия пользования", None, TERMS_URL, None),
            ("🔒 Политика конфиденциальности", None, PRIVACY_URL, None),
        ],
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


async def test_apples_status_shows_progress_and_always_offers_spend_action():
    from src.handlers.apples import process_apples_status

    payments = FakePayments(
        apple_status=AppleStatus(
            balance=37,
            eligible_purchase_count=4,
            level="Садовник",
            rate_percent=10,
            next_level_purchase_count=7,
            purchases_to_next_level=3,
            is_max_level=False,
            redeemable_days=2,
            missing_apples=0,
            has_existing_key=True,
        )
    )
    callback = FakeCallback(user_id=42, data="apples_status")

    await process_apples_status(callback, make_deps(payments=payments))

    assert callback.answers == [((), {})]
    assert payments.apple_status_calls == [42]
    text, markup = callback.message.edits[0]
    assert text == (
        "🍏 <b>Мои яблоки</b>\n\n"
        "Баланс: <b>37 🍏</b>\n"
        "Покупок MTProxy: <b>4</b>\n"
        "Уровень: <b>Садовник</b>\n"
        "Кэшбэк: <b>10%</b>\n"
        "До следующего уровня: <b>3</b>\n\n"
        "Курс: <b>15 🍏 = 1 день</b>"
    )
    assert [
        [(button.text, button.callback_data) for button in row]
        for row in markup.inline_keyboard
    ] == [
        [("🍏 Потратить яблоки", "apples_spend")],
        [("🔙 Назад", "show_mtproxy_menu")],
    ]


async def test_apples_status_shows_max_level_without_progress_count():
    from src.handlers.apples import process_apples_status

    payments = FakePayments(
        apple_status=AppleStatus(
            balance=7,
            eligible_purchase_count=8,
            level="Мастер сада",
            rate_percent=15,
            next_level_purchase_count=None,
            purchases_to_next_level=None,
            is_max_level=True,
            redeemable_days=0,
            missing_apples=8,
            has_existing_key=False,
        )
    )
    callback = FakeCallback(user_id=42, data="apples_status")

    await process_apples_status(callback, make_deps(payments=payments))

    text, markup = callback.message.edits[0]
    assert "Максимальный уровень достигнут" in text
    assert "До следующего уровня" not in text
    assert markup.inline_keyboard[0][0].callback_data == "apples_spend"


async def test_apples_spend_offers_one_day_and_all_saved_backend_modes():
    from src.handlers.apples import process_apples_spend

    payments = FakePayments(
        apple_status=AppleStatus(
            balance=37,
            eligible_purchase_count=7,
            level="Мастер сада",
            rate_percent=15,
            next_level_purchase_count=None,
            purchases_to_next_level=None,
            is_max_level=True,
            redeemable_days=2,
            missing_apples=0,
            has_existing_key=True,
        )
    )
    callback = FakeCallback(user_id=42, data="apples_spend")

    await process_apples_spend(callback, make_deps(payments=payments))

    assert payments.apple_status_calls == [42]
    assert payments.apple_preview_calls == []
    text, markup = callback.message.edits[0]
    assert "Баланс: <b>37 🍏</b>" in text
    assert "Доступно дней: <b>2</b>" in text
    assert [
        [(button.text, button.callback_data) for button in row]
        for row in markup.inline_keyboard
    ] == [
        [("Обменять на 1 день — 15 🍏", "apples_redeem_one")],
        [("Обменять все яблоки", "apples_redeem_all")],
        [("🔙 Назад", "apples_status")],
    ]


async def test_apples_spend_below_rate_shows_exact_missing_count_without_preview():
    from src.handlers.apples import process_apples_spend

    payments = FakePayments(
        apple_status=AppleStatus(
            balance=7,
            eligible_purchase_count=0,
            level="Новичок",
            rate_percent=5,
            next_level_purchase_count=4,
            purchases_to_next_level=4,
            is_max_level=False,
            redeemable_days=0,
            missing_apples=8,
            has_existing_key=True,
        )
    )
    callback = FakeCallback(user_id=42, data="apples_spend")

    await process_apples_spend(callback, make_deps(payments=payments))

    text, markup = callback.message.edits[0]
    assert text == (
        "🍏 Для обмена не хватает <b>8 🍏</b>.\n"
        "Курс: <b>15 🍏 = 1 день</b>"
    )
    assert payments.apple_preview_calls == []
    assert [[button.callback_data for button in row] for row in markup.inline_keyboard] == [
        ["apples_status"]
    ]


async def test_apples_spend_without_existing_key_stops_before_preview():
    from src.handlers.apples import process_apples_spend

    payments = FakePayments(
        apple_status=AppleStatus(
            balance=30,
            eligible_purchase_count=1,
            level="Новичок",
            rate_percent=5,
            next_level_purchase_count=4,
            purchases_to_next_level=3,
            is_max_level=False,
            redeemable_days=2,
            missing_apples=0,
            has_existing_key=False,
        )
    )
    callback = FakeCallback(user_id=42, data="apples_spend")

    await process_apples_spend(callback, make_deps(payments=payments))

    text, markup = callback.message.edits[0]
    assert text == (
        "🍏 Яблоки можно потратить только на продление "
        "своего существующего MTProxy-ключа."
    )
    assert payments.apple_preview_calls == []
    assert markup.inline_keyboard[0][0].callback_data == "apples_status"


@pytest.mark.parametrize(
    ("handler_name", "callback_data", "mode", "apples_spent", "days"),
    [
        ("process_apples_redeem_one", "apples_redeem_one", "one_day", 15, 1),
        ("process_apples_redeem_all", "apples_redeem_all", "all", 30, 2),
    ],
)
async def test_apples_preview_uses_only_saved_quote_and_requires_confirmation(
    handler_name: str,
    callback_data: str,
    mode: str,
    apples_spent: int,
    days: int,
):
    from src.handlers import apples as apples_module

    payments = FakePayments(
        apple_preview=AppleRedemptionPreview(
            confirmation_id=501,
            mode=mode,
            apples_spent=apples_spent,
            days=days,
            projected_expired_date="2026-08-21",
        )
    )
    callback = FakeCallback(user_id=42, data=callback_data)

    await getattr(apples_module, handler_name)(
        callback,
        make_deps(payments=payments),
    )

    assert payments.apple_preview_calls == [(42, mode)]
    assert payments.apple_confirm_calls == []
    text, markup = callback.message.edits[0]
    assert f"Списать: <b>{apples_spent} 🍏</b>" in text
    assert f"Добавить дней: <b>{days}</b>" in text
    assert "Продление до: <b>2026-08-21</b>" in text
    assert "Подтвердить обмен?" in text
    assert [
        [(button.text, button.callback_data) for button in row]
        for row in markup.inline_keyboard
    ] == [
        [("✅ Подтвердить", "apples_confirm:501")],
        [("🔙 Назад", "apples_spend")],
    ]


async def test_apples_confirm_renders_committed_37_to_30_two_days_and_7_balance():
    from src.handlers.apples import process_apples_confirm

    payments = FakePayments(
        apple_result=AppleRedemptionResult(
            apples_spent=30,
            days=2,
            expired_date="2026-08-22",
            balance=7,
        )
    )
    callback = FakeCallback(user_id=42, data="apples_confirm:501")

    await process_apples_confirm(callback, make_deps(payments=payments))

    assert payments.apple_confirm_calls == [(42, 501)]
    text, markup = callback.message.edits[0]
    assert text == (
        "✅ <b>Яблоки обменены</b>\n\n"
        "Списано: <b>30 🍏</b>\n"
        "Добавлено дней: <b>2</b>\n"
        "Продление до: <b>2026-08-22</b>\n"
        "Баланс: <b>7 🍏</b>"
    )
    assert [[button.callback_data for button in row] for row in markup.inline_keyboard] == [
        ["apples_status"],
        ["show_mtproxy_menu"],
    ]


async def test_repeated_apples_confirmation_displays_same_committed_result():
    from src.handlers.apples import process_apples_confirm

    payments = FakePayments(
        apple_result=AppleRedemptionResult(
            apples_spent=15,
            days=1,
            expired_date="2026-08-21",
            balance=0,
        )
    )
    callbacks = [
        FakeCallback(user_id=42, data="apples_confirm:777"),
        FakeCallback(user_id=42, data="apples_confirm:777"),
    ]

    for callback in callbacks:
        await process_apples_confirm(callback, make_deps(payments=payments))

    assert payments.apple_confirm_calls == [(42, 777), (42, 777)]
    assert callbacks[0].message.edits[0][0] == callbacks[1].message.edits[0][0]
    assert "Продление до: <b>2026-08-21</b>" in (
        callbacks[1].message.edits[0][0]
    )


async def test_apples_preview_and_stale_confirm_preserve_backend_safe_errors():
    from src.handlers.apples import (
        process_apples_confirm,
        process_apples_redeem_one,
    )

    no_key = APIError(
        42,
        message="Для обмена яблок нужен существующий MTProxy-ключ.",
    )
    preview_payments = FakePayments(apple_preview_error=no_key)
    preview_callback = FakeCallback(user_id=42, data="apples_redeem_one")

    with pytest.raises(APIError) as preview_exc:
        await process_apples_redeem_one(
            preview_callback,
            make_deps(payments=preview_payments),
        )

    assert preview_exc.value is no_key
    assert preview_callback.message.edits == []

    stale = APIError(
        42,
        message="Условия обмена изменились. Создайте новый предпросмотр.",
    )
    confirm_payments = FakePayments(apple_confirm_error=stale)
    confirm_callback = FakeCallback(user_id=42, data="apples_confirm:501")

    with pytest.raises(APIError) as confirm_exc:
        await process_apples_confirm(
            confirm_callback,
            make_deps(payments=confirm_payments),
        )

    assert confirm_exc.value is stale
    assert confirm_payments.apple_confirm_calls == [(42, 501)]
    assert confirm_callback.message.edits == []


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
        ["🌐 Наш сайт"],
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
        [button.callback_data for button in row]
        for row in markup.inline_keyboard
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
    assert "2026-08-01" in text


# --- legal documents --------------------------------------------------------


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

    assert [row[0].callback_data for row in markup.inline_keyboard] == expected_callbacks
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
def test_unknown_payment_method_keeps_only_back(
    builder, kwargs, back_callback
) -> None:
    markup = builder(**kwargs)

    assert [row[0].callback_data for row in markup.inline_keyboard] == [
        back_callback
    ]


def test_root_menu_links_to_common_destinations():
    markup = keyboards.product_menu()

    urls = [btn.url for row in markup.inline_keyboard for btn in row if btn.url]
    assert SUPPORT_URL == "https://t.me/mtprotokeys_support"
    assert "https://t.me/mtprotokeys_support" in urls
    assert "https://mtprotokeys.com" in urls
    assert set(urls) == {SITE_URL, SUPPORT_URL, TERMS_URL, PRIVACY_URL}


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
        keyboards.confirm_reissue().inline_keyboard[-1][0].callback_data
        == "my_servers"
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


# --- links ------------------------------------------------------------------


async def test_process_my_servers_renders_server_buttons(servers: MyServers):
    fake = FakeLinks(servers=servers)
    callback = FakeCallback(chat_id=42)

    await process_my_servers(callback, make_deps(links=fake))

    assert fake.get_calls == ["42"]
    text, markup = callback.message.edits[0]
    assert "2026-07-14" in text
    assert markup.inline_keyboard[0][0].text == "🇳🇱 Нидерланды"
    assert markup.inline_keyboard[0][0].url == "tg://proxy?a=1"


async def test_update_link_shows_confirmation_without_reissuing(servers: MyServers):
    fake = FakeLinks(servers=servers)
    callback = FakeCallback(chat_id=42)

    await update_link(callback, make_deps(links=fake))

    # tapping «Перевыпустить» only opens the confirmation screen — nothing reissued
    assert fake.reissue_calls == []
    assert fake.get_calls == []
    _, markup = callback.message.edits[0]
    callbacks = [btn.callback_data for row in markup.inline_keyboard for btn in row]
    assert "update_link_confirm" in callbacks


async def test_confirm_reissue_reissues_and_shows_servers_with_banner(servers: MyServers):
    fake = FakeLinks(servers=servers)
    callback = FakeCallback(chat_id=42)

    await update_link_confirm(callback, make_deps(links=fake))

    assert fake.reissue_calls == ["42"]
    assert fake.get_calls == ["42"]
    text, markup = callback.message.edits[0]
    assert "перевыпущен" in text.lower()  # success banner is shown
    assert markup.inline_keyboard[0][0].text == "🇳🇱 Нидерланды"  # server buttons present


# --- referrals --------------------------------------------------------------


def _cabinet(active: int) -> ReferralCabinet:
    return ReferralCabinet(
        total_referrals_count=active + 2,
        active_referrals_count=active,
        referral_link="https://t.me/bot?start=42",
        link_activated_count=0,
    )


@pytest.mark.parametrize(
    ("active_referrals_count", "expected_rows"),
    [
        (
            5,
            [
                [
                    (
                        "🎁 Получить 14 дней MTProxy",
                        "get-referral-link",
                        None,
                        None,
                        "success",
                    )
                ],
                [
                    (
                        "🔗 Поделиться ссылкой",
                        None,
                        None,
                        "Привет! Переходи по моей реферальной ссылке: "
                        "https://t.me/bot?start=42",
                        "primary",
                    )
                ],
                [("🔙 Главное меню", "show_start_screen", None, None, None)],
            ],
        ),
        (
            4,
            [
                [
                    (
                        "🔗 Поделиться ссылкой",
                        None,
                        None,
                        "Привет! Переходи по моей реферальной ссылке: "
                        "https://t.me/bot?start=42",
                        "primary",
                    )
                ],
                [("🔙 Главное меню", "show_start_screen", None, None, None)],
            ],
        ),
    ],
)
async def test_referral_navigation_matches_reward_eligibility(
    active_referrals_count,
    expected_rows,
):
    fake = FakeReferrals(cabinet=_cabinet(active=active_referrals_count))
    callback = FakeCallback(chat_id=42)

    await process_referral(callback, make_deps(referrals=fake))

    text, markup = callback.message.edits[0]
    assert text.strip().splitlines()[0] == "<b>Реферальная программа</b>"
    assert [
        [
            (
                button.text,
                button.callback_data,
                button.url,
                button.switch_inline_query,
                button.style,
            )
            for button in row
        ]
        for row in markup.inline_keyboard
    ] == expected_rows


async def test_referral_reward_result_matches_domain_boundary():
    fake = FakeReferrals(
        cabinet=_cabinet(active=5),
        reward=ReferralRewardKey(expired_date="2026-06-30"),
    )
    callback = FakeCallback(chat_id=42)

    await process_referral_link(callback, make_deps(referrals=fake))

    assert fake.reward_calls == ["42"]
    text, markup = callback.message.answers[0]
    assert "14 дней MTProxy" in text
    assert "2026-06-30" in text
    assert [
        [(button.text, button.callback_data, button.style) for button in row]
        for row in markup.inline_keyboard
    ] == [
        [("⚡ Перейти в MTProxy", "show_mtproxy_menu", "success")],
        [("🔙 Реферальная программа", "referral", None)],
    ]
    assert not any(
        button.callback_data == "my_servers"
        for row in markup.inline_keyboard
        for button in row
    )


# --- payments ---------------------------------------------------------------


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
        [(*button_by_method[code], style)]
        for code, style in expected_method_styles
    ]
    expected_rows.append([(*back_button, None)])
    actual_rows = [
        [(button.text, button.callback_data, button.style) for button in row]
        for row in markup.inline_keyboard
    ]
    assert actual_rows == expected_rows
    assert text == (
        normal_text if methods else "Оплата временно недоступна"
    )
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
def test_sbp_fractional_rub_label_uses_comma_and_primary_style(
    builder, kwargs
) -> None:
    button = builder(**kwargs).inline_keyboard[0][0]

    assert button.text == "⚡ СБП — 99,50 ₽"
    assert button.style == "primary"


@pytest.mark.parametrize(
    ("handler_module", "handler_name", "callback_data"),
    [
        (payments_module, "process_pay_yukassa", "pay_yukassa"),
        (payments_module, "process_gift_yukassa", "gift_yukassa"),
        (vpn_module, "process_vpn_pay_yukassa", "vpn_pay_yukassa"),
    ],
)
async def test_legacy_yukassa_callbacks_are_safe_noops(
    monkeypatch, handler_module, handler_name, callback_data
):
    fake_bot = FakeBot()
    monkeypatch.setattr(payments_module, "bot", fake_bot)
    monkeypatch.setattr(vpn_module, "bot", fake_bot)
    handler = getattr(handler_module, handler_name)
    callback = FakeCallback(data=callback_data)

    await handler(callback)

    assert tuple(inspect.signature(handler).parameters) == ("callback",)
    assert callback.answers == [((), {})]
    assert callback.message.answers == []
    assert callback.message.edits == []
    assert fake_bot.invoices == []


async def test_vpn_navigation_matches_approved_hierarchy():
    callback = FakeCallback(data="show_vpn_menu")

    await process_vpn_menu(callback)

    assert callback.answers
    text, markup = callback.message.edits[0]
    assert text == """🔐 <b>VPN от MTProto Keys</b>

🌐 Защищённое подключение к интернету
📱 Работает на Android, iOS, Windows и macOS
🔗 Постоянная subscription-ссылка
⚙️ Подключение через приложение HAPP

👇 Выберите действие:"""
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
        [button.callback_data for button in row]
        for row in markup.inline_keyboard
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
                expired_at="2026-08-31T12:00:00+00:00",
                subscription_url="https://vpn.example/subscriptions/active/",
            ),
            """🔐 <b>Твоя VPN-подписка активна</b>

Действует до: <b>2026-08-31T12:00:00+00:00</b>

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

Она действовала до: <b>2026-07-31T12:00:00+00:00</b>

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
    vpn = FakeVPN(
        menu=VPNMenu(status="none", expired_at=None, subscription_url=None)
    )
    deps = _deps_with_vpn(vpn=vpn)

    with pytest.raises(VPNSubscriptionDoesNotExist) as exc_info:
        await process_vpn_subscription(callback, deps)

    assert callback.answers
    assert vpn.menu_calls == ["42"]
    assert deps.payments.vpn_stars_invoice_calls == 0
    assert callback.message.edits == []
    assert exc_info.value.telegram_id == "42"
    assert exc_info.value.message == (
        "🔒 У вас нет активной VPN-подписки. Если вы думаете, что это ошибка, "
        "пожалуйста, напишите в поддержку: @mtprotokeys_support."
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
    vpn = FakeVPN(
        menu=VPNMenu(status="none", expired_at=None, subscription_url=None)
    )

    with pytest.raises(VPNSubscriptionDoesNotExist) as exc_info:
        await process_vpn_reissue(callback, _deps_with_vpn(vpn=vpn))

    assert callback.answers
    assert vpn.menu_calls == ["42"]
    assert vpn.reissue_calls == []
    assert callback.message.edits == []
    assert exc_info.value.telegram_id == "42"
    assert exc_info.value.message == (
        "🔒 У вас нет активной VPN-подписки. Если вы думаете, что это ошибка, "
        "пожалуйста, напишите в поддержку: @mtprotokeys_support."
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
    error = APIError("42", message="🔒 Пожалуйста, подождите 5 минут с последнего обновления.")
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
            vpn=FakeVPN(menu=VPNMenu(status="none", expired_at=None, subscription_url=None)),
            payments=FakePayments(stars=stars),
        ),
    )

    invoice = fake_bot.invoices[0]
    assert invoice["payload"] == "vpn_stars"
    assert invoice["currency"] == "XTR"
    assert invoice["prices"][0].amount == 149


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
    monkeypatch, handler, purchase_kind: str, back_callback: str,
) -> None:
    fake_bot = FakeBot()
    monkeypatch.setattr(payments_module, "bot", fake_bot)
    monkeypatch.setattr(vpn_module, "bot", fake_bot)
    payments = FakePayments(
        crypto=CryptoInvoice(
            invoice_url="https://t.me/CryptoBot?start=x",
            rub_amount="99.00",
            expires_at="2026-08-02T12:30:00Z",
            reused=False,
        )
    )
    callback = FakeCallback(user_id=42)

    await handler(callback, make_deps(payments=payments))

    assert callback.answers == [((), {})]
    assert payments.crypto_calls == [(42, purchase_kind)]
    assert fake_bot.invoices == []
    text, markup = callback.message.edits[0]
    assert "99.00" in text
    assert "2026-08-02T12:30:00Z" in text
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
    assert "99.50" in text
    assert "Срок действия счета: 15 минут" in text
    assert "2026-08-08T12:15:00Z" not in text
    assert "Возврат в бот не подтверждает оплату" not in text
    assert (
        "Результат будет выдан автоматически после подтверждения платежа."
        in text
    )
    assert markup.inline_keyboard[0][0].text == "Оплатить через СБП"
    assert markup.inline_keyboard[0][0].url == (
        "https://pay.example/invoice/opaque"
    )
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


@pytest.mark.parametrize(
    ("currency", "expected_charge_id", "expected_provider"),
    [("XTR", "ch_stars", "stars"), ("RUB", "ch_card", "yukassa")],
)
async def test_successful_payment_preserves_provider_and_charge_id(
    currency, expected_charge_id, expected_provider
):
    payments = FakePayments()
    message = FakeMessage(user_id=42)
    message.successful_payment = SimpleNamespace(
        currency=currency,
        telegram_payment_charge_id="ch_stars",
        provider_payment_charge_id="ch_card",
    )

    await process_successful_payment(message, make_deps(payments=payments))

    assert payments.confirmed == [(42, expected_charge_id, expected_provider)]


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
    assert "Подписка активна до: <b>2026-09-18</b>" in text
    assert "Начислено: <b>5 🍏</b>" in text
    assert "Ставка: <b>5%</b>" in text
    assert "Баланс: <b>20 🍏</b>" in text
    assert "Уровень: <b>Садовник</b>" in text
    assert "🎉 Новый уровень: <b>Садовник</b>" in text
    assert "Кэшбэк следующей покупки: <b>10%</b>" in text
    assert [button.callback_data for row in markup.inline_keyboard for button in row] == [
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
        currency="RUB",
        invoice_payload="gift_certificate_yukassa",
        telegram_payment_charge_id="unused",
        provider_payment_charge_id="gift_charge",
    )

    await process_successful_payment(message, make_deps(payments=payments))

    assert payments.gift_confirmed == [(42, "gift_charge", "yukassa")]
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
    payload = "payment_stars" if purchase_kind == "subscription" else "gift_certificate_stars"
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
        currency="RUB",
        invoice_payload="gift_certificate_yukassa",
        telegram_payment_charge_id="ch_stars",
        provider_payment_charge_id="gift_ch_card",
    )

    await process_successful_payment(message, make_deps(payments=payments))

    assert payments.gift_confirmed == [(42, "gift_ch_card", "yukassa")]
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
        ("RUB", "vpn_yukassa", "vpn_ch_card", "yukassa"),
    ],
)
async def test_successful_vpn_payment_shows_approved_parent_actions(
    currency, invoice_payload, expected_charge_id, expected_provider
):
    payments = FakePayments()
    vpn = FakeVPN(
        menu=VPNMenu(status="none", expired_at=None, subscription_url=None),
        purchase=VPNPurchase(
            expired_at="2026-08-31T12:00:00+00:00",
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

    await process_successful_payment(message, _deps_with_vpn(vpn=vpn, payments=payments))

    assert vpn.purchase_calls == [(42, expected_charge_id, expected_provider)]
    assert payments.confirmed == []
    text, markup = message.answers[0]
    assert "2026-08-31T12:00:00+00:00" in text
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
    assert "08.08.26" in text


async def test_gift_certificate_activation_failure_uses_support_contact():
    payments = FakePayments(activation_error=RuntimeError("boom"))
    message = FakeMessage(user_id=42, text="KEY-ABCD-1234")

    await process_gift_certificate_activation(message, make_deps(payments=payments))

    text, _ = message.answers[0]
    assert "@mtprotokeys_support" in text
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
    assert "обратитесь в поддержку" in text
    assert "@mtprotokeys_support" in text
    assert "@mtproto_keys" not in text


async def test_pre_checkout_query_is_approved(monkeypatch):
    fake_bot = FakeBot()
    monkeypatch.setattr(payments_module, "bot", fake_bot)
    pre_checkout = SimpleNamespace(id="q1")

    await process_pre_checkout_query(pre_checkout)

    args, kwargs = fake_bot.pre_checkout[0]
    assert args[0] == "q1"
    assert kwargs["ok"] is True
