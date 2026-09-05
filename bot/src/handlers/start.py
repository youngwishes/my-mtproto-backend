from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from src import keyboards
from src.enums import FreeAvailable
from src.exceptions import APIError
from src.handlers.apples import render_apple_spend_screen
from src.messages import (
    FAQ_TEXT,
    FREE_AVAILABLE_TEXT_MAPPING,
    LEGAL_CONSENT_TEXT,
    PRODUCT_MENU_TEXT,
)

if TYPE_CHECKING:
    from src.dependencies import Dependencies

router = Router()


def _render_start_screen() -> tuple[str, InlineKeyboardMarkup]:
    return PRODUCT_MENU_TEXT, keyboards.product_menu()


async def _render_mtproxy_menu(
    *,
    deps: Dependencies,
    telegram_id: str,
    telegram_username: str | None,
) -> tuple[str, InlineKeyboardMarkup]:
    available_free_period = await deps.free_trial.check_availability(
        telegram_id=telegram_id,
        telegram_username=telegram_username,
        invited_from_username=None,
    )
    text = FREE_AVAILABLE_TEXT_MAPPING.get(available_free_period)
    is_free = available_free_period != FreeAvailable.NOT_AVAILABLE
    boost_callback_data = "boost_free" if is_free else "boost_paid"
    return text, keyboards.mtproxy_menu(boost_callback_data)


@router.message(Command("start"))
async def cmd_start(message: Message, deps: Dependencies):
    invited_from_username = None
    try:
        referrer_id = int(message.text.split()[-1])
        if referrer_id != message.from_user.id:
            invited_from_username = str(referrer_id)
    except ValueError:
        pass
    telegram_id = str(message.from_user.id)
    consent_accepted = await deps.free_trial.get_consent_status(
        telegram_id=telegram_id
    )
    if not consent_accepted:
        await message.answer(
            text=LEGAL_CONSENT_TEXT,
            reply_markup=keyboards.legal_consent(invited_from_username),
        )
        return
    if message.text.split()[1:] == ["apples_spend"]:
        text, keyboard = await render_apple_spend_screen(
            deps=deps,
            telegram_id=message.from_user.id,
        )
    else:
        text, keyboard = _render_start_screen()
    await message.answer(text=text, reply_markup=keyboard)


@router.callback_query(
    (F.data == keyboards.LEGAL_CONSENT_CALLBACK)
    | F.data.startswith(f"{keyboards.LEGAL_CONSENT_CALLBACK}:")
)
async def process_legal_consent(
    callback: CallbackQuery,
    deps: Dependencies,
) -> None:
    await callback.answer()
    telegram_id = str(callback.from_user.id)
    _, separator, raw_referrer = (callback.data or "").partition(":")
    invited_from_username = (
        raw_referrer if separator and raw_referrer.isdigit() else None
    )
    if invited_from_username == telegram_id:
        invited_from_username = None

    accepted = await deps.free_trial.accept_consent(
        telegram_id=telegram_id,
        telegram_username=callback.from_user.username,
        invited_from_username=invited_from_username,
    )
    if accepted is not True:
        raise APIError(telegram_id, error="Legal consent was not saved.")

    text, keyboard = _render_start_screen()
    await callback.message.edit_text(text=text, reply_markup=keyboard)


@router.callback_query(F.data == "show_start_screen")
async def cmd_start_inline(callback: CallbackQuery) -> None:
    await callback.answer()
    text, keyboard = _render_start_screen()
    await callback.message.edit_text(text=text, reply_markup=keyboard)


@router.callback_query(F.data == "show_mtproxy_menu")
async def process_mtproxy_menu(
    callback: CallbackQuery, deps: Dependencies
) -> None:
    await callback.answer()
    text, keyboard = await _render_mtproxy_menu(
        deps=deps,
        telegram_id=str(callback.from_user.id),
        telegram_username=callback.from_user.username,
    )
    await callback.message.edit_text(text=text, reply_markup=keyboard)


@router.callback_query(F.data == "info")
async def process_info(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(text=FAQ_TEXT, reply_markup=keyboards.info())
