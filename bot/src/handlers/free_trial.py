from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.types import CallbackQuery

from src import keyboards
from src.messages import KEY_GENERATED_TEXT

if TYPE_CHECKING:
    from src.dependencies import Dependencies

router = Router()


@router.callback_query(F.data == "boost_free")
async def process_boost_free(callback: CallbackQuery, deps: Dependencies):
    await callback.answer()
    key = await deps.free_trial.claim(telegram_id=str(callback.message.chat.id))
    await callback.message.edit_text(
        text=KEY_GENERATED_TEXT.format(expired_date=key.expired_date),
        reply_markup=keyboards.key_generated(),
    )
