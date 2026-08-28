from __future__ import annotations

import pytest
from src.domains.referrals import ReferralCabinet, ReferralRewardKey
from src.handlers.referrals import process_referral, process_referral_link

from tests.fakes import FakeCallback, make_deps
from tests.handler_support import (
    FakeReferrals,
)


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
    assert "30.06.2026" in text
    assert "2026-06-30" not in text
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
