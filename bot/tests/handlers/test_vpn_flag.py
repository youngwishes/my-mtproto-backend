from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.domains.vpn import VPNMenu
from src.handlers.start import cmd_start
from src.handlers.payments import process_pre_checkout_query
from src.handlers import payments
from tests.fakes import FakeBot, FakeMessage, make_deps
from tests.handler_support import FakeFreeTrial, FakeVPN


@pytest.mark.parametrize("enabled", [False, True])
async def test_start_reads_current_flag_and_hides_vpn_text_and_button(enabled):
    vpn = FakeVPN(
        menu=VPNMenu(status="none", expired_at=None, subscription_url=None),
        enabled=enabled,
    )
    deps = make_deps(vpn=vpn, free_trial=FakeFreeTrial(consent=True))
    for state in (enabled, not enabled):
        vpn.enabled = state
        message = FakeMessage()
        await cmd_start(message, deps)
        text, markup = message.answers[0]
        assert ("VPN" in text) is state
        callbacks = [
            button.callback_data for row in markup.inline_keyboard for button in row
        ]
        assert ("show_vpn_menu" in callbacks) is state
        assert "show_mtproxy_menu" in callbacks


@pytest.mark.parametrize("enabled", [False, True])
async def test_old_stars_invoice_checks_flag_before_accepting_payment(
    monkeypatch, enabled
):
    bot = FakeBot()
    monkeypatch.setattr(payments, "bot", bot)
    vpn = FakeVPN(
        menu=VPNMenu(status="none", expired_at=None, subscription_url=None),
        enabled=enabled,
    )
    query = SimpleNamespace(
        id="old-invoice", currency="XTR", invoice_payload="vpn_stars"
    )
    await process_pre_checkout_query(query, make_deps(vpn=vpn))
    assert bot.pre_checkout[0][1]["ok"] is enabled


@pytest.mark.parametrize(
    "callback_data",
    [
        "show_vpn_menu",
        "vpn",
        "vpn_subscription",
        "vpn_reissue",
        "vpn_reissue_confirm",
        "vpn_pay_stars",
        "vpn_pay_crypto",
        "vpn_pay_platega_sbp",
    ],
)
async def test_old_vpn_buttons_return_to_mtproxy_root_without_side_effects(
    callback_data,
):
    from src.handlers.vpn import router
    from tests.fakes import FakeCallback

    vpn = FakeVPN(
        menu=VPNMenu(
            status="active",
            expired_at="2026-12-01",
            subscription_url="https://example.org/sub",
        ),
        enabled=False,
    )
    callback = FakeCallback(data=callback_data)
    await router.propagate_event(
        update_type="callback_query", event=callback, deps=make_deps(vpn=vpn)
    )
    assert callback.answers
    text, markup = callback.message.edits[0]
    assert "VPN" not in text
    assert "show_vpn_menu" not in [
        b.callback_data for row in markup.inline_keyboard for b in row
    ]
    assert vpn.menu_calls == vpn.reissue_calls == vpn.purchase_calls == []


async def test_enabled_vpn_router_still_opens_section():
    from src.handlers.vpn import router
    from tests.fakes import FakeCallback

    callback = FakeCallback(data="show_vpn_menu")
    await router.propagate_event(
        update_type="callback_query", event=callback, deps=make_deps()
    )
    assert "VPN" in callback.message.edits[0][0]


async def test_paid_vpn_is_fulfilled_silently_when_disabled():
    from src.handlers.payments import process_successful_payment

    vpn = FakeVPN(
        menu=VPNMenu(status="none", expired_at=None, subscription_url=None),
        enabled=False,
    )
    message = FakeMessage()
    message.successful_payment = SimpleNamespace(
        telegram_payment_charge_id="paid", invoice_payload="vpn_stars"
    )
    await process_successful_payment(message, make_deps(vpn=vpn))
    assert vpn.purchase_calls == [(42, "paid", "stars")]
    assert message.answers == []


@pytest.mark.parametrize("entrypoint", ["back", "consent"])
async def test_disabled_vpn_stays_hidden_on_other_root_entrypoints(entrypoint):
    from src.handlers.start import cmd_start_inline, process_legal_consent
    from tests.fakes import FakeCallback

    vpn = FakeVPN(
        menu=VPNMenu(status="none", expired_at=None, subscription_url=None),
        enabled=False,
    )
    deps = make_deps(vpn=vpn, free_trial=FakeFreeTrial(consent=False))
    callback = FakeCallback(
        data="accept_legal_terms" if entrypoint == "consent" else "show_start_screen"
    )
    handler = process_legal_consent if entrypoint == "consent" else cmd_start_inline
    await handler(callback, deps)
    text, markup = callback.message.edits[0]
    assert "VPN" not in text
    assert "show_vpn_menu" not in [
        b.callback_data for row in markup.inline_keyboard for b in row
    ]
