from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from src import keyboards
from src.enums import FreeAvailable
from src.exceptions import APIError
from src.messages import FAQ_TEXT, FREE_AVAILABLE_TEXT_MAPPING, LEGAL_CONSENT_TEXT

if TYPE_CHECKING:
    from src.dependencies import Dependencies

router = Router()
_MAX_REFERRER_DIGITS = 20


def _normalise_referrer(
    *,
    raw_referrer: str | None,
    telegram_id: str,
) -> str | None:
    if (
        raw_referrer is None
        or not raw_referrer.isascii()
        or not raw_referrer.isdigit()
        or len(raw_referrer) > _MAX_REFERRER_DIGITS
    ):
        return None

    referrer = raw_referrer.lstrip("0") or "0"
    current_user = telegram_id.lstrip("0") or "0"
    return None if referrer == current_user else referrer


def _start_referrer(*, text: str | None, telegram_id: str) -> str | None:
    parts = (text or "").split(maxsplit=1)
    raw_referrer = parts[1] if len(parts) == 2 else None
    return _normalise_referrer(
        raw_referrer=raw_referrer,
        telegram_id=telegram_id,
    )


def _callback_referrer(*, data: str | None, telegram_id: str) -> str | None:
    prefix = f"{keyboards.LEGAL_CONSENT_CALLBACK}:"
    raw_referrer = (
        data.removeprefix(prefix) if data and data.startswith(prefix) else None
    )
    return _normalise_referrer(
        raw_referrer=raw_referrer,
        telegram_id=telegram_id,
    )


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
async def cmd_start(message: Message, deps: Dependencies) -> None:
    telegram_id = str(message.from_user.id)
    invited_from_username = _start_referrer(
        text=message.text,
        telegram_id=telegram_id,
    )
    consent_status = await deps.consent.get_status(telegram_id=telegram_id)
    if not consent_status.legal_terms_accepted:
        await message.answer(
            text=LEGAL_CONSENT_TEXT,
            reply_markup=keyboards.legal_consent(invited_from_username),
        )
        return

    text, keyboard = await _render_start_screen(
        deps=deps,
        telegram_id=telegram_id,
        telegram_username=message.from_user.username,
        invited_from_username=invited_from_username,
    )
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
    invited_from_username = _callback_referrer(
        data=callback.data,
        telegram_id=telegram_id,
    )
    consent_status = await deps.consent.accept(
        telegram_id=telegram_id,
        telegram_username=callback.from_user.username,
        invited_from_username=invited_from_username,
    )
    if getattr(consent_status, "legal_terms_accepted", None) is not True:
        raise APIError(
            telegram_id,
            error="Invalid legal consent accept result.",
        )
    text, keyboard = await _render_start_screen(
        deps=deps,
        telegram_id=telegram_id,
        telegram_username=callback.from_user.username,
        invited_from_username=None,
    )
    await callback.message.edit_text(text=text, reply_markup=keyboard)


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
