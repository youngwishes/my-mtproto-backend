from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from aiogram.types import LabeledPrice

from src import keyboards
from src.exceptions import APIError
from src.handlers import payments as payments_module
from src.handlers.free_trial import process_boost_free
from src.handlers.links import process_my_servers, update_link, update_link_confirm
from src.handlers.payments import (
    process_gift_certificate,
    process_gift_certificate_activation,
    process_gift_stars,
    process_gift_yukassa,
    process_boost_paid,
    process_pay_stars,
    process_pay_yukassa,
    process_pre_checkout_query,
    process_successful_payment,
)
from src.handlers.vpn import process_vpn, process_vpn_pay_stars, process_vpn_pay_yukassa
from src.handlers.referrals import process_referral, process_referral_link
from src.handlers.start import (
    cmd_start,
    cmd_start_inline,
    process_info,
    process_legal_consent,
)
from src.messages import PRIVACY_URL, SITE_URL, SUPPORT_URL, TERMS_URL
from src.domains.free_trial import FreeTrialKey
from src.domains.links import MyServers, ReissuedKey, ServerItem
from src.domains.payments import (
    ActivatedGiftCertificate,
    CardInvoice,
    GiftCertificate,
    StarsInvoice,
)
from src.domains.referrals import ReferralCabinet, ReferralRewardKey
from src.domains.vpn import VPNMenu, VPNPurchase
from tests.fakes import FakeBot, FakeCallback, FakeMessage, make_deps


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
        card=None,
        stars=None,
        gift=None,
        activation=None,
        confirm_error=None,
        activation_error=None,
    ) -> None:
        self._card = card
        self._stars = stars
        self._gift = gift or GiftCertificate(code="KEY-ABCD-1234")
        self._activation = activation or ActivatedGiftCertificate(
            expired_date="2026-08-08"
        )
        self._confirm_error = confirm_error
        self._activation_error = activation_error
        self.confirmed: list[tuple] = []
        self.gift_confirmed: list[tuple] = []
        self.activated: list[tuple] = []

    async def get_card_invoice(self):
        return self._card

    async def get_stars_invoice(self):
        return self._stars

    async def get_vpn_card_invoice(self):
        return self._card

    async def get_vpn_stars_invoice(self):
        return self._stars

    async def confirm_purchase(self, *, telegram_id, charge_id, provider):
        self.confirmed.append((telegram_id, charge_id, provider))
        if self._confirm_error is not None:
            raise self._confirm_error

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


class FakeVPN:
    def __init__(self, *, menu: VPNMenu, purchase: VPNPurchase | None = None) -> None:
        self._menu = menu
        self._purchase = purchase or VPNPurchase(
            expired_at="2026-08-31T12:00:00+00:00",
            subscription_url="https://vpn.example/subscriptions/token/",
        )
        self.menu_calls: list[str] = []
        self.purchase_calls: list[tuple] = []

    async def get_menu(self, *, telegram_id):
        self.menu_calls.append(telegram_id)
        return self._menu

    async def confirm_purchase(self, *, telegram_id, charge_id, provider):
        self.purchase_calls.append((telegram_id, charge_id, provider))
        return self._purchase


def _deps_with_vpn(*, vpn: FakeVPN, payments: FakePayments | None = None):
    from src.dependencies import Dependencies

    if payments is None:
        payments = FakePayments(
            card=CardInvoice(
                title="VPN на месяц",
                description="VPN-подписка",
                currency="RUB",
                provider_data="{}",
                send_email_to_provider=False,
                need_email=False,
                prices=[LabeledPrice(label="VPN на месяц", amount=14900)],
                provider_token="PROV",
            ),
            stars=StarsInvoice(
                title="VPN на месяц",
                description="VPN-подписка",
                prices=[LabeledPrice(label="VPN на месяц", amount=149)],
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


async def test_cmd_start_offers_free_boost_when_available():
    fake = FakeFreeTrial(check="MONTH")
    message = FakeMessage(text="/start", user_id=42, username="bob")

    await cmd_start(message, make_deps(free_trial=fake))

    assert fake.checked == [("42", "bob", None)]
    _, markup = message.answers[0]
    assert markup.inline_keyboard[0][0].callback_data == "boost_free"


async def test_cmd_start_offers_paid_boost_when_not_available():
    fake = FakeFreeTrial(check="NOT_AVAILABLE")
    message = FakeMessage(text="/start")

    await cmd_start(message, make_deps(free_trial=fake))

    _, markup = message.answers[0]
    assert markup.inline_keyboard[0][0].callback_data == "boost_paid"


async def test_cmd_start_passes_none_username_as_none_not_string():
    # У юзера нет @username в Telegram → шлём None, а не str(None) == "None"
    fake = FakeFreeTrial(check="MONTH")
    message = FakeMessage(text="/start", user_id=42, username=None)

    await cmd_start(message, make_deps(free_trial=fake))

    assert fake.checked[0][1] is None


async def test_cmd_start_extracts_referrer_from_payload():
    fake = FakeFreeTrial()
    message = FakeMessage(text="/start 777", user_id=42)

    await cmd_start(message, make_deps(free_trial=fake))

    assert fake.checked[0][2] == "777"  # invited_from_username


async def test_cmd_start_ignores_self_referral():
    fake = FakeFreeTrial()
    message = FakeMessage(text="/start 42", user_id=42)

    await cmd_start(message, make_deps(free_trial=fake))

    assert fake.checked[0][2] is None


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
    assert fake.checked == [("42", "real_user", None)]
    assert callback.message.edits


async def test_accept_consent_does_not_open_menu_when_backend_returns_false():
    fake = FakeFreeTrial(consent=False, accept_result=False)
    callback = FakeCallback(user_id=42, data="accept_legal_terms")

    with pytest.raises(APIError):
        await process_legal_consent(callback, make_deps(free_trial=fake))

    assert fake.checked == []
    assert callback.message.edits == []


async def test_show_start_screen_answers_callback():
    # «🔙 Назад» (show_start_screen) must close the loading spinner in Telegram
    fake = FakeFreeTrial(check="MONTH")
    callback = FakeCallback(chat_id=42)

    await cmd_start_inline(callback, make_deps(free_trial=fake))

    assert callback.answers, "callback.answer() was not called — spinner hangs"


async def test_show_start_screen_passes_clicking_user_not_bot():
    # id и username берутся у нажавшего (callback.from_user), а не из
    # сообщения с кнопкой (callback.message), которое принадлежит боту
    fake = FakeFreeTrial(check="MONTH")
    callback = FakeCallback(chat_id=99, user_id=42, username="real_user")

    await cmd_start_inline(callback, make_deps(free_trial=fake))

    telegram_id, telegram_username, _ = fake.checked[0]
    assert telegram_id == "42"
    assert telegram_username == "real_user"


async def test_info_answers_callback():
    callback = FakeCallback(chat_id=42)

    await process_info(callback)

    assert callback.answers


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

    await process_boost_paid(callback)

    text, _ = callback.message.edits[0]
    assert TERMS_URL in text
    assert PRIVACY_URL in text


def test_main_menu_last_button_links_to_site():
    markup = keyboards.main_menu("boost_free")

    last_button = markup.inline_keyboard[-1][-1]
    assert last_button.url == SITE_URL


def test_main_menu_has_support_button():
    markup = keyboards.main_menu("boost_free")

    urls = [btn.url for row in markup.inline_keyboard for btn in row if btn.url]
    assert SUPPORT_URL in urls


def test_main_menu_opens_vpn_subscription_management():
    markup = keyboards.main_menu("boost_free")

    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert "vpn" in callbacks


def test_info_keyboard_links_to_legal_docs_and_drops_offer():
    markup = keyboards.info()

    urls = [btn.url for row in markup.inline_keyboard for btn in row if btn.url]
    assert TERMS_URL in urls
    assert PRIVACY_URL in urls
    assert not any("drive.google.com" in url for url in urls)


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


async def test_referral_shows_reward_button_at_threshold():
    fake = FakeReferrals(cabinet=_cabinet(active=5))
    callback = FakeCallback(chat_id=42)

    await process_referral(callback, make_deps(referrals=fake))

    _, markup = callback.message.edits[0]
    texts = [btn.text for row in markup.inline_keyboard for btn in row]
    assert "🎁 Получить бесплатную ссылку" in texts


async def test_referral_hides_reward_button_below_threshold():
    fake = FakeReferrals(cabinet=_cabinet(active=4))
    callback = FakeCallback(chat_id=42)

    await process_referral(callback, make_deps(referrals=fake))

    _, markup = callback.message.edits[0]
    texts = [btn.text for row in markup.inline_keyboard for btn in row]
    assert "🎁 Получить бесплатную ссылку" not in texts


async def test_referral_link_claims_reward():
    fake = FakeReferrals(
        cabinet=_cabinet(active=5),
        reward=ReferralRewardKey(expired_date="2026-06-30"),
    )
    callback = FakeCallback(chat_id=42)

    await process_referral_link(callback, make_deps(referrals=fake))

    assert fake.reward_calls == ["42"]
    text, _ = callback.message.answers[0]
    assert "2026-06-30" in text


# --- payments ---------------------------------------------------------------


@pytest.mark.parametrize("status", ["none", "expired"])
async def test_vpn_menu_offers_two_payment_methods_for_unavailable_subscription(status):
    callback = FakeCallback(chat_id=42)
    vpn = FakeVPN(
        menu=VPNMenu(
            status=status,
            expired_at="2026-07-31T12:00:00+00:00" if status == "expired" else None,
            subscription_url="https://vpn.example/subscriptions/token/" if status == "expired" else None,
        )
    )

    await process_vpn(callback, _deps_with_vpn(vpn=vpn))

    text, markup = callback.message.edits[0]
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert vpn.menu_calls == ["42"]
    assert "vpn_pay_yukassa" in callbacks
    assert "vpn_pay_stars" in callbacks
    if status == "expired":
        assert "2026-07-31T12:00:00+00:00" in text


@pytest.mark.parametrize(
    ("status", "expired_at", "subscription_url"),
    [
        ("none", None, None),
        (
            "expired",
            "2026-07-31T12:00:00+00:00",
            "https://vpn.example/subscriptions/token/",
        ),
        (
            "active",
            "2026-08-31T12:00:00+00:00",
            "https://vpn.example/subscriptions/token/",
        ),
    ],
)
async def test_vpn_menu_shows_current_prices_for_every_subscription_state(
    status, expired_at, subscription_url
):
    card = CardInvoice(
        title="VPN на месяц",
        description="VPN-подписка",
        currency="RUB",
        provider_data="{}",
        send_email_to_provider=False,
        need_email=False,
        prices=[LabeledPrice(label="VPN на месяц", amount=17345)],
        provider_token="PROV",
    )
    stars = StarsInvoice(
        title="VPN на месяц",
        description="VPN-подписка",
        prices=[LabeledPrice(label="VPN на месяц", amount=237)],
    )
    callback = FakeCallback(chat_id=42)

    await process_vpn(
        callback,
        _deps_with_vpn(
            vpn=FakeVPN(
                menu=VPNMenu(
                    status=status,
                    expired_at=expired_at,
                    subscription_url=subscription_url,
                )
            ),
            payments=FakePayments(card=card, stars=stars),
        ),
    )

    _, markup = callback.message.edits[0]
    buttons = {
        button.callback_data: button.text
        for row in markup.inline_keyboard
        for button in row
    }
    assert buttons["vpn_pay_yukassa"] == "💳 ЮKassa — 173,45 ₽"
    assert buttons["vpn_pay_stars"] == "⭐ Telegram Stars — 237 ★"


async def test_vpn_menu_shows_active_expiry_and_stable_subscription_url():
    callback = FakeCallback(chat_id=42)
    vpn = FakeVPN(
        menu=VPNMenu(
            status="active",
            expired_at="2026-08-31T12:00:00+00:00",
            subscription_url="https://vpn.example/subscriptions/token/",
        )
    )

    await process_vpn(callback, _deps_with_vpn(vpn=vpn))

    text, _ = callback.message.edits[0]
    assert "2026-08-31T12:00:00+00:00" in text
    assert "https://vpn.example/subscriptions/token/" in text
    _, markup = callback.message.edits[0]
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert "vpn_pay_yukassa" in callbacks
    assert "vpn_pay_stars" in callbacks


async def test_vpn_yukassa_invoice_uses_distinct_payload_and_vpn_product(monkeypatch):
    fake_bot = FakeBot()
    monkeypatch.setattr("src.handlers.vpn.bot", fake_bot)
    provider_data = {
        "receipt": {
            "customer": {},
            "items": [
                {
                    "description": "Оплата VPN-подписки на один месяц.",
                    "quantity": "1.00",
                    "amount": {"value": 149, "currency": "RUB"},
                    "vat_code": 4,
                    "payment_mode": "full_payment",
                },
            ],
        }
    }
    card = CardInvoice(
        title="VPN на 30 дней",
        description="VPN-подписка",
        currency="RUB",
        provider_data=json.dumps(provider_data),
        send_email_to_provider=True,
        need_email=True,
        prices=[LabeledPrice(label="VPN на 30 дней", amount=14900)],
        provider_token="PROV",
    )

    await process_vpn_pay_yukassa(
        FakeCallback(chat_id=42),
        _deps_with_vpn(
            vpn=FakeVPN(menu=VPNMenu(status="none", expired_at=None, subscription_url=None)),
            payments=FakePayments(card=card),
        ),
    )

    invoice = fake_bot.invoices[0]
    assert invoice["payload"] == "vpn_yukassa"
    assert invoice["prices"][0].amount == 14900
    assert json.loads(invoice["provider_data"]) == provider_data
    assert invoice["need_email"] is True
    assert invoice["send_email_to_provider"] is True


async def test_vpn_stars_invoice_uses_distinct_payload_and_vpn_product(monkeypatch):
    fake_bot = FakeBot()
    monkeypatch.setattr("src.handlers.vpn.bot", fake_bot)
    stars = StarsInvoice(
        title="VPN на месяц",
        description="VPN-подписка",
        prices=[LabeledPrice(label="VPN на месяц", amount=149)],
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


async def test_pay_yukassa_sends_card_invoice(monkeypatch):
    fake_bot = FakeBot()
    monkeypatch.setattr(payments_module, "bot", fake_bot)
    card = CardInvoice(
        title="Месяц",
        description="прокси",
        currency="RUB",
        provider_data="{}",
        send_email_to_provider=False,
        need_email=False,
        prices=[LabeledPrice(label="Месяц", amount=9900)],
        provider_token="PROV",
    )
    callback = FakeCallback(chat_id=42)

    await process_pay_yukassa(callback, make_deps(payments=FakePayments(card=card)))

    invoice = fake_bot.invoices[0]
    assert invoice["chat_id"] == 42
    assert invoice["provider_token"] == "PROV"
    assert invoice["prices"][0].amount == 9900


async def test_pay_stars_sends_xtr_invoice(monkeypatch):
    fake_bot = FakeBot()
    monkeypatch.setattr(payments_module, "bot", fake_bot)
    stars = StarsInvoice(
        title="Месяц",
        description="прокси",
        prices=[LabeledPrice(label="Месяц", amount=80)],
    )
    callback = FakeCallback(chat_id=42)

    await process_pay_stars(callback, make_deps(payments=FakePayments(stars=stars)))

    invoice = fake_bot.invoices[0]
    assert invoice["currency"] == "XTR"
    assert invoice["prices"][0].amount == 80


async def test_gift_certificate_screen_shows_payment_options():
    callback = FakeCallback(chat_id=42)

    await process_gift_certificate(callback)

    text, markup = callback.message.edits[0]
    assert "сертификат" in text.lower()
    callbacks = [btn.callback_data for row in markup.inline_keyboard for btn in row]
    assert "gift_yukassa" in callbacks
    assert "gift_stars" in callbacks


async def test_gift_yukassa_invoice_uses_gift_payload(monkeypatch):
    fake_bot = FakeBot()
    monkeypatch.setattr(payments_module, "bot", fake_bot)
    card = CardInvoice(
        title="Месяц",
        description="прокси",
        currency="RUB",
        provider_data=json.dumps(
            {"receipt": {"items": [{"description": "Обычная подписка"}]}}
        ),
        send_email_to_provider=False,
        need_email=False,
        prices=[LabeledPrice(label="Месяц", amount=9900)],
        provider_token="PROV",
    )
    callback = FakeCallback(chat_id=42)

    await process_gift_yukassa(callback, make_deps(payments=FakePayments(card=card)))

    invoice = fake_bot.invoices[0]
    assert invoice["payload"] == "gift_certificate_yukassa"
    assert "сертификат" in invoice["title"].lower()
    provider_data = json.loads(invoice["provider_data"])
    description = provider_data["receipt"]["items"][0]["description"]
    assert "сертификат" in description.lower()


async def test_gift_stars_invoice_uses_gift_payload(monkeypatch):
    fake_bot = FakeBot()
    monkeypatch.setattr(payments_module, "bot", fake_bot)
    stars = StarsInvoice(
        title="Месяц",
        description="прокси",
        prices=[LabeledPrice(label="Месяц", amount=80)],
    )
    callback = FakeCallback(chat_id=42)

    await process_gift_stars(callback, make_deps(payments=FakePayments(stars=stars)))

    invoice = fake_bot.invoices[0]
    assert invoice["payload"] == "gift_certificate_stars"
    assert invoice["currency"] == "XTR"


@pytest.mark.parametrize(
    "currency,expected_provider",
    [("XTR", "stars"), ("RUB", "yukassa")],
)
async def test_successful_payment_routes_by_currency(currency, expected_provider):
    payments = FakePayments()
    message = FakeMessage(user_id=42)
    message.successful_payment = SimpleNamespace(
        currency=currency,
        telegram_payment_charge_id="ch_stars",
        provider_payment_charge_id="ch_card",
    )

    await process_successful_payment(message, make_deps(payments=payments))

    _, _, provider = payments.confirmed[0]
    assert provider == expected_provider


async def test_successful_gift_payment_returns_code_to_forward():
    payments = FakePayments(gift=GiftCertificate(code="KEY-ABCD-1234"))
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


async def test_successful_vpn_payment_routes_only_to_vpn_buy_and_shows_happ_import():
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
        currency="XTR",
        invoice_payload="vpn_stars",
        telegram_payment_charge_id="vpn_ch_stars",
        provider_payment_charge_id="vpn_ch_card",
    )

    await process_successful_payment(message, _deps_with_vpn(vpn=vpn, payments=payments))

    assert vpn.purchase_calls == [(42, "vpn_ch_stars", "stars")]
    assert payments.confirmed == []
    text, _ = message.answers[0]
    assert "2026-08-31T12:00:00+00:00" in text
    assert "https://vpn.example/subscriptions/token/" in text
    assert "Android" in text
    assert "iOS" in text
    assert "Windows" in text
    assert "macOS" in text


async def test_gift_certificate_code_message_activates_certificate():
    payments = FakePayments(
        activation=ActivatedGiftCertificate(expired_date="08.08.26")
    )
    message = FakeMessage(user_id=42, text="KEY-ABCD-1234")

    await process_gift_certificate_activation(message, make_deps(payments=payments))

    assert payments.activated == [(42, "KEY-ABCD-1234")]
    text, _ = message.answers[0]
    assert "08.08.26" in text


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


async def test_pre_checkout_query_is_approved(monkeypatch):
    fake_bot = FakeBot()
    monkeypatch.setattr(payments_module, "bot", fake_bot)
    pre_checkout = SimpleNamespace(id="q1")

    await process_pre_checkout_query(pre_checkout)

    args, kwargs = fake_bot.pre_checkout[0]
    assert args[0] == "q1"
    assert kwargs["ok"] is True
