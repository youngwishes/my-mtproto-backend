from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery

from src import keyboards
from src.bot import bot
from src.messages import PAYMENT_METHODS_TEXT

if TYPE_CHECKING:
    from src.dependencies import Dependencies

router = Router()


@router.callback_query(F.data == "boost_paid")
async def process_boost_paid(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        text=PAYMENT_METHODS_TEXT,
        reply_markup=keyboards.payment_methods(),
    )


@router.callback_query(F.data == "pay_yukassa")
async def process_pay_yukassa(callback: CallbackQuery, deps: Dependencies):
    await callback.answer()
    invoice = await deps.payments.get_card_invoice()
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        start_parameter="payment",
        payload="payment",
        **invoice.asdict(),
    )


@router.callback_query(F.data == "pay_stars")
async def process_pay_stars(callback: CallbackQuery, deps: Dependencies):
    await callback.answer()
    invoice = await deps.payments.get_stars_invoice()
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=invoice.title,
        description=invoice.description,
        start_parameter="payment_stars",
        payload="payment_stars",
        currency=invoice.currency,
        prices=invoice.prices,
        provider_token=invoice.provider_token,
    )


@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message, deps: Dependencies):
    if message.successful_payment.currency == "XTR":
        charge_id = message.successful_payment.telegram_payment_charge_id
        provider = "stars"
    else:
        charge_id = message.successful_payment.provider_payment_charge_id
        provider = "yukassa"

    try:
        await deps.payments.confirm_purchase(
            telegram_id=message.from_user.id,
            charge_id=charge_id,
            provider=provider,
        )
    except Exception:
        await message.answer(
            "⚠️ Оплата получена, но произошла ошибка при выдаче ключа.\n"
            "Пожалуйста, обратитесь в поддержку: @mtproto_keys"
        )
