from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery

from src import keyboards
from src.bot import bot
from src.messages import (
    GIFT_CERTIFICATE_ACTIVATED_TEXT,
    GIFT_CERTIFICATE_PURCHASED_TEXT,
    GIFT_CERTIFICATE_TEXT,
    PAYMENT_METHODS_TEXT,
    VPN_PURCHASED_TEXT,
)

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
async def process_pay_yukassa(callback: CallbackQuery) -> None:
    await callback.answer()


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


@router.callback_query(F.data == "gift_certificate")
async def process_gift_certificate(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        text=GIFT_CERTIFICATE_TEXT,
        reply_markup=keyboards.gift_certificate_payment_methods(),
    )


@router.callback_query(F.data == "gift_yukassa")
async def process_gift_yukassa(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "gift_stars")
async def process_gift_stars(callback: CallbackQuery, deps: Dependencies):
    await callback.answer()
    invoice = await deps.payments.get_stars_invoice()
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title="Подарочный сертификат MTPRoto Keys — 30 дней",
        description="Одноразовый код на 30 дней подписки",
        start_parameter="gift_certificate_stars",
        payload="gift_certificate_stars",
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

    payload = getattr(message.successful_payment, "invoice_payload", "")

    try:
        if payload in {"vpn_yukassa", "vpn_stars"}:
            if deps.vpn is None:
                raise RuntimeError("VPN client is not configured")
            purchase = await deps.vpn.confirm_purchase(
                telegram_id=message.from_user.id,
                charge_id=charge_id,
                provider=provider,
            )
            await message.answer(
                VPN_PURCHASED_TEXT.format(
                    expired_at=purchase.expired_at,
                    subscription_url=purchase.subscription_url,
                )
            )
            return
        if payload.startswith("gift_certificate"):
            certificate = await deps.payments.confirm_gift_certificate_purchase(
                telegram_id=message.from_user.id,
                charge_id=charge_id,
                provider=provider,
            )
            await message.answer(
                GIFT_CERTIFICATE_PURCHASED_TEXT.format(code=certificate.code)
            )
            return
        await deps.payments.confirm_purchase(
            telegram_id=message.from_user.id,
            charge_id=charge_id,
            provider=provider,
        )
    except Exception:
        purchase_item = (
            "VPN-подписки"
            if payload in {"vpn_yukassa", "vpn_stars"}
            else "сертификата"
            if payload.startswith("gift_certificate")
            else "ключа"
        )
        await message.answer(
            f"⚠️ Оплата получена, но произошла ошибка при выдаче {purchase_item}.\n"
            "Пожалуйста, обратитесь в поддержку: @mtproto_keys"
        )


@router.message(F.text.regexp(r"^\s*KEY-[A-Za-z0-9]{4}-[A-Za-z0-9]{4}\s*$"))
async def process_gift_certificate_activation(message: Message, deps: Dependencies):
    try:
        result = await deps.payments.activate_gift_certificate(
            telegram_id=message.from_user.id,
            code=message.text,
        )
    except Exception as exc:
        error_message = getattr(exc, "message", None) or (
            "Не удалось активировать сертификат. Напишите в поддержку: @mtproto_keys"
        )
        await message.answer(error_message)
        return
    await message.answer(
        GIFT_CERTIFICATE_ACTIVATED_TEXT.format(expired_date=result.expired_date),
        reply_markup=keyboards.key_generated(),
    )
