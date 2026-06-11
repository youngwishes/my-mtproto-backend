from __future__ import annotations

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    Message,
    PreCheckoutQuery,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot import bot
from domains.payments.client import get_payments_client
from domains.payments.messages import PAYMENT_ERROR_TEXT, PAYMENT_SELECTION_TEXT

router = Router()


@router.callback_query(F.data == "boost_paid")
async def process_boost_paid(callback: CallbackQuery) -> None:
    await callback.answer()
    keyboard = InlineKeyboardBuilder(
        markup=[
            [InlineKeyboardButton(text="💳 ЮKassa — 79 ₽", callback_data="pay_yukassa")],
            [InlineKeyboardButton(text="⭐ Telegram Stars — 60 ★", callback_data="pay_stars")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="show_start_screen")],
        ],
    )
    await callback.message.edit_text(
        text=PAYMENT_SELECTION_TEXT,
        parse_mode="HTML",
        reply_markup=keyboard.adjust(1).as_markup(),
    )


@router.callback_query(F.data == "pay_yukassa")
async def process_pay_yukassa(callback: CallbackQuery) -> None:
    await callback.answer()
    client = get_payments_client()
    response = await client.get_invoice_data()
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        start_parameter="payment",
        payload="payment",
        **response.asdict(),
    )


@router.callback_query(F.data == "pay_stars")
async def process_pay_stars(callback: CallbackQuery) -> None:
    await callback.answer()
    client = get_payments_client()
    response = await client.get_stars_invoice_data()
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=response.title,
        description=response.description,
        start_parameter="payment_stars",
        payload="payment_stars",
        currency=response.currency,
        prices=response.prices,
        provider_token=response.provider_token,
    )


@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery) -> None:
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message) -> None:
    if message.successful_payment.currency == "XTR":
        charge_id = message.successful_payment.telegram_payment_charge_id
        provider = "stars"
    else:
        charge_id = message.successful_payment.provider_payment_charge_id
        provider = "yukassa"

    try:
        client = get_payments_client()
        await client.record_purchase(
            telegram_id=message.from_user.id,
            charge_id=charge_id,
            provider=provider,
        )
    except Exception:
        await message.answer(PAYMENT_ERROR_TEXT)
