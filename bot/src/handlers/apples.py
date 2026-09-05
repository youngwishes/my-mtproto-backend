from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.types import CallbackQuery

from src import keyboards
from src.config import settings
from src.messages import (
    APPLE_KEY_REQUIRED_TEXT,
    render_apple_redemption_preview,
    render_apple_redemption_result,
    render_apple_spend,
    render_apple_status,
    render_insufficient_apples,
)

if TYPE_CHECKING:
    from aiogram.types import InlineKeyboardMarkup

    from src.dependencies import Dependencies

router = Router()


@router.callback_query(F.data == "apples_status")
async def process_apples_status(
    callback: CallbackQuery,
    deps: Dependencies,
) -> None:
    await callback.answer()
    status = await deps.payments.get_apple_status(
        telegram_id=callback.from_user.id,
    )
    await callback.message.edit_text(
        text=render_apple_status(status=status),
        reply_markup=keyboards.apples_status(
            fortune_wheel_url=settings.fortune_wheel_url,
        ),
    )


@router.callback_query(F.data == "apples_spend_referral")
@router.callback_query(F.data == "apples_spend")
async def process_apples_spend(
    callback: CallbackQuery,
    deps: Dependencies,
) -> None:
    await callback.answer()
    back_callback_data = (
        "referral" if callback.data == "apples_spend_referral" else "apples_status"
    )
    text, keyboard = await render_apple_spend_screen(
        deps=deps,
        telegram_id=callback.from_user.id,
        back_callback_data=back_callback_data,
    )
    await callback.message.edit_text(text=text, reply_markup=keyboard)


async def render_apple_spend_screen(
    *,
    deps: Dependencies,
    telegram_id: int,
    back_callback_data: str = "apples_status",
) -> tuple[str, InlineKeyboardMarkup]:
    status = await deps.payments.get_apple_status(telegram_id=telegram_id)
    if not status.has_existing_key:
        return APPLE_KEY_REQUIRED_TEXT, keyboards.apples_back_to_status(
            back_callback_data=back_callback_data,
        )
    if status.missing_apples:
        return render_insufficient_apples(
            missing_apples=status.missing_apples,
        ), keyboards.apples_back_to_status(back_callback_data=back_callback_data)
    return render_apple_spend(
        balance=status.balance,
        redeemable_days=status.redeemable_days,
    ), keyboards.apples_spend(back_callback_data=back_callback_data)


async def _process_apple_redemption_preview(
    *,
    callback: CallbackQuery,
    deps: Dependencies,
    mode: str,
) -> None:
    await callback.answer()
    preview = await deps.payments.preview_apple_redemption(
        telegram_id=callback.from_user.id,
        mode=mode,
    )
    await callback.message.edit_text(
        text=render_apple_redemption_preview(preview=preview),
        reply_markup=keyboards.apples_redemption_confirmation(
            confirmation_id=preview.confirmation_id,
        ),
    )


@router.callback_query(F.data == "apples_redeem_one")
async def process_apples_redeem_one(
    callback: CallbackQuery,
    deps: Dependencies,
) -> None:
    await _process_apple_redemption_preview(
        callback=callback,
        deps=deps,
        mode="one_day",
    )


@router.callback_query(F.data == "apples_redeem_all")
async def process_apples_redeem_all(
    callback: CallbackQuery,
    deps: Dependencies,
) -> None:
    await _process_apple_redemption_preview(
        callback=callback,
        deps=deps,
        mode="all",
    )


@router.callback_query(F.data.regexp(r"^apples_confirm:\d+$"))
async def process_apples_confirm(
    callback: CallbackQuery,
    deps: Dependencies,
) -> None:
    await callback.answer()
    confirmation_id = int(callback.data.split(":", maxsplit=1)[1])
    result = await deps.payments.confirm_apple_redemption(
        telegram_id=callback.from_user.id,
        confirmation_id=confirmation_id,
    )
    await callback.message.edit_text(
        text=render_apple_redemption_result(result=result),
        reply_markup=keyboards.apples_redemption_done(),
    )
