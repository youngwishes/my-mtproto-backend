from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from src import keyboards
from src.enums import FreeAvailable
from src.messages import FAQ_TEXT, FREE_AVAILABLE_TEXT_MAPPING

if TYPE_CHECKING:
    from src.dependencies import Dependencies

router = Router()


async def _render_start_screen(
    *,
    deps: Dependencies,
    telegram_id: str,
    telegram_username: str | None,
    invited_from_username: str | None,
) -> tuple[str, InlineKeyboardMarkup]:
    available_free_period = await deps.free_trial.check_availability(
        telegram_id=telegram_id,
        telegram_username=telegram_username,
        invited_from_username=invited_from_username,
    )
    text = FREE_AVAILABLE_TEXT_MAPPING.get(available_free_period)
    is_free = available_free_period != FreeAvailable.NOT_AVAILABLE
    boost_callback_data = "boost_free" if is_free else "boost_paid"
    return text, keyboards.main_menu(boost_callback_data)


@router.message(Command("start"))
async def cmd_start(message: Message, deps: Dependencies):
    invited_from_username = None
    try:
        referrer_id = int(message.text.split()[-1])
        if referrer_id != message.from_user.id:
            invited_from_username = str(referrer_id)
    except ValueError:
        pass
    text, keyboard = await _render_start_screen(
        deps=deps,
        telegram_id=str(message.from_user.id),
        telegram_username=message.from_user.username,
        invited_from_username=invited_from_username,
    )
    await message.answer(text=text, reply_markup=keyboard)


@router.callback_query(F.data == "show_start_screen")
async def cmd_start_inline(callback: CallbackQuery, deps: Dependencies):
    await callback.answer()
    text, keyboard = await _render_start_screen(
        deps=deps,
        telegram_id=str(callback.from_user.id),
        telegram_username=callback.from_user.username,
        invited_from_username=None,
    )
    await callback.message.edit_text(text=text, reply_markup=keyboard)


@router.callback_query(F.data == "info")
async def process_info(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(text=FAQ_TEXT, reply_markup=keyboards.info())
