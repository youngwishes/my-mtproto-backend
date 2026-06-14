from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.types import CallbackQuery

from src import keyboards
from src.messages import KEY_GENERATED_TEXT, REFERRAL_CABINET

if TYPE_CHECKING:
    from src.dependencies import Dependencies

router = Router()


@router.callback_query(F.data == "referral")
async def process_referral(callback: CallbackQuery, deps: Dependencies):
    await callback.answer()
    cabinet = await deps.referrals.get_cabinet(telegram_id=str(callback.message.chat.id))
    await callback.message.edit_text(
        text=REFERRAL_CABINET.format(
            total_referrals_count=cabinet.total_referrals_count,
            active_referrals_count=cabinet.active_referrals_count,
            referral_link=cabinet.referral_link,
        ),
        reply_markup=keyboards.referral_cabinet(
            active_referrals_count=cabinet.active_referrals_count,
            referral_link=cabinet.referral_link,
        ),
    )


@router.callback_query(F.data == "get-referral-link")
async def process_referral_link(callback: CallbackQuery, deps: Dependencies):
    await callback.answer()
    key = await deps.referrals.claim_reward(telegram_id=str(callback.message.chat.id))
    await callback.message.answer(
        text=KEY_GENERATED_TEXT.format(expired_date=key.expired_date),
        reply_markup=keyboards.referral_reward(),
    )
