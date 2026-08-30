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
    assert text == (
        "\n<b>🤝 Реферальная программа</b>\n\n"
        "Приглашай друзей и получай яблоки:\n\n"
        "👥 Приглашено: <b>7</b>\n"
        "✅ Получили пробный доступ: <b>5</b>\n"
        "🍏 На балансе: <b>75</b>\n\n"
        "Друг получает <b>14 дней бесплатно</b>, а ты — <b>15 🍏</b> "
        "после активации его пробного периода.\n\n"
        "<b>Твоя ссылка:</b>\n"
        "https://t.me/bot?start=42\n"
    )
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
        [
            (
                "🍏 Потратить яблоки",
                "apples_spend_referral",
                None,
                None,
                "success",
            )
        ],
        [("🔙 Главное меню", "show_start_screen", None, None, None)],
    ]
