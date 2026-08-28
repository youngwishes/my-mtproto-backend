from __future__ import annotations

from src.domains.referrals import ReferralCabinet
from src.handlers.referrals import process_referral

from tests.fakes import FakeCallback, make_deps
from tests.handler_support import (
    FakeReferrals,
)


def _cabinet() -> ReferralCabinet:
    return ReferralCabinet(
        total_referrals_count=7,
        active_referrals_count=5,
        referral_link="https://t.me/bot?start=42",
        apple_balance=75,
    )


async def test_referral_cabinet_shows_apple_program():
    fake = FakeReferrals(cabinet=_cabinet())
    callback = FakeCallback(chat_id=42)

    await process_referral(callback, make_deps(referrals=fake))

    text, markup = callback.message.edits[0]
    assert "Общее количество приглашённых: <b>7</b>" in text
    assert "Активировали пробный период: <b>5</b>" in text
    assert "Баланс яблок: <b>75 🍏</b>" in text
    assert "https://t.me/bot?start=42" in text
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
    ] == [
        [("🍏 Потратить яблоки", "apples_spend", None, None, "success")],
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
    ]
