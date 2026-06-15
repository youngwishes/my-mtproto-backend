from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram.types import LabeledPrice

from src import keyboards
from src.handlers import payments as payments_module
from src.handlers.free_trial import process_boost_free
from src.handlers.links import process_my_servers, update_link, update_link_confirm
from src.handlers.payments import (
    process_boost_paid,
    process_pay_stars,
    process_pay_yukassa,
    process_pre_checkout_query,
    process_successful_payment,
)
from src.handlers.referrals import process_referral, process_referral_link
from src.handlers.start import cmd_start
from src.messages import PRIVACY_URL, SITE_URL, SUPPORT_URL, TERMS_URL
from src.domains.free_trial import FreeTrialKey
from src.domains.links import MyServers, ReissuedKey, ServerItem
from src.domains.payments import CardInvoice, StarsInvoice
from src.domains.referrals import ReferralCabinet, ReferralRewardKey
from tests.fakes import FakeBot, FakeCallback, FakeMessage, make_deps


# --- domain fakes -----------------------------------------------------------


class FakeFreeTrial:
    def __init__(self, *, check="MONTH", key=None) -> None:
        self._check = check
        self._key = key or FreeTrialKey(expired_date="2026-07-14")
        self.checked: list[tuple] = []
        self.claimed: list[str] = []

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
    def __init__(self, *, card=None, stars=None, confirm_error=None) -> None:
        self._card = card
        self._stars = stars
        self._confirm_error = confirm_error
        self.confirmed: list[tuple] = []

    async def get_card_invoice(self):
        return self._card

    async def get_stars_invoice(self):
        return self._stars

    async def confirm_purchase(self, *, telegram_id, charge_id, provider):
        self.confirmed.append((telegram_id, charge_id, provider))
        if self._confirm_error is not None:
            raise self._confirm_error


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
