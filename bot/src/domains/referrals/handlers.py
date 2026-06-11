from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from domains.referrals.client import get_referrals_client
from domains.referrals.messages import KEY_GENERATED_TEXT, REFERRAL_CABINET

router = Router()


@router.callback_query(F.data == "referral")
async def process_referral(callback: CallbackQuery) -> None:
    await callback.answer()
    client = get_referrals_client()
    response = await client.get_cabinet(telegram_id=str(callback.message.chat.id))

    keyboard: list[list[InlineKeyboardButton]] = []
    if response.active_referrals_count is not None and response.active_referrals_count >= 5:
        keyboard.append(
            [InlineKeyboardButton(text="🎁 Получить бесплатную ссылку", callback_data="get-referral-link")]
        )
    keyboard.append(
        [InlineKeyboardButton(
            text="🔗 Поделиться ссылкой",
            switch_inline_query=f"Привет! Переходи по моей реферальной ссылке: {response.referral_link}",
        )]
    )
    keyboard.append(
        [InlineKeyboardButton(text="🔙 Назад", callback_data="show_start_screen")]
    )

    await callback.message.edit_text(
        text=REFERRAL_CABINET.format(
            total_referrals_count=response.total_referrals_count,
            active_referrals_count=response.active_referrals_count,
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
    )


@router.callback_query(F.data == "get-referral-link")
async def process_referral_link(callback: CallbackQuery) -> None:
    await callback.answer()
    client = get_referrals_client()
    response = await client.get_referral_link(telegram_id=str(callback.message.chat.id))
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇳🇱 Подключиться", url=response.link)],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="show_start_screen")],
        ]
    )
    await callback.message.edit_text(
        text=KEY_GENERATED_TEXT.format(expired_date=response.expired_date),
        parse_mode="HTML",
        reply_markup=keyboard,
    )
