from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from domains.links.client import get_links_client
from domains.links.messages import KEY_UPDATED_TEXT

router = Router()


@router.callback_query(F.data == "update_link")
async def update_link(callback: CallbackQuery) -> None:
    await callback.answer()
    client = get_links_client()
    response = await client.update(telegram_id=str(callback.message.chat.id))
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇳🇱 Подключиться", url=response.link)],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="show_start_screen")],
        ]
    )
    await callback.message.edit_text(
        text=KEY_UPDATED_TEXT.format(expired_date=response.expired_date),
        parse_mode="HTML",
        reply_markup=keyboard,
    )
