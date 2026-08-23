from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    PreCheckoutQuery,
)

from src import keyboards
from src.bot import bot
from src.exceptions import APIError
from src.domains.payments import HistoricalPurchaseReplay
from src.messages import (
    CRYPTO_INVOICE_ERROR_TEXT,
    CRYPTO_INVOICE_TEXT,
    GIFT_CERTIFICATE_ACTIVATED_TEXT,
    GIFT_CERTIFICATE_PURCHASED_TEXT,
    GIFT_CERTIFICATE_TEXT,
    MTPROXY_PURCHASED_CTA,
    MTPROXY_PURCHASED_TEXT,
    PAYMENT_METHODS_TEXT,
    PLATEGA_INVOICE_ERROR_TEXT,
    PLATEGA_INVOICE_TEXT,
    VPN_PURCHASED_TEXT,
    render_apple_purchase_outcome,
)
from src.presentation import (
    format_rub_amount,
    format_user_date,
    format_user_datetime,
)

if TYPE_CHECKING:
    from src.dependencies import Dependencies

router = Router()


async def show_crypto_invoice(
    *,
    callback: CallbackQuery,
    deps: Dependencies,
    purchase_kind: str,
    back_callback: str,
) -> None:
    await callback.answer()
    try:
        invoice = await deps.payments.create_crypto_invoice(
            telegram_id=callback.from_user.id,
            purchase_kind=purchase_kind,
        )
    except APIError:
        await callback.message.answer(CRYPTO_INVOICE_ERROR_TEXT)
        return
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть CryptoBot",
                    url=invoice.invoice_url,
                )
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback)],
        ]
    )
    await callback.message.edit_text(
        text=CRYPTO_INVOICE_TEXT.format(
            rub_amount=format_rub_amount(invoice.rub_amount),
            expires_at=format_user_datetime(invoice.expires_at),
        ),
        reply_markup=markup,
    )


async def show_platega_invoice(
    *,
    callback: CallbackQuery,
    deps: Dependencies,
    purchase_kind: str,
    back_callback: str,
) -> None:
    await callback.answer()
    try:
        invoice = await deps.payments.create_platega_invoice(
            telegram_id=callback.from_user.id,
            purchase_kind=purchase_kind,
        )
    except APIError:
        await callback.message.answer(PLATEGA_INVOICE_ERROR_TEXT)
        return
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Оплатить через СБП",
                    url=invoice.payment_url,
                )
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback)],
        ]
    )
    await callback.message.edit_text(
        text=PLATEGA_INVOICE_TEXT.format(
            rub_amount=format_rub_amount(invoice.rub_amount),
        ),
        reply_markup=markup,
    )


@router.callback_query(F.data == "boost_paid")
async def process_boost_paid(callback: CallbackQuery, deps: Dependencies):
    await callback.answer()
    invoice = await deps.payments.get_stars_invoice()
    await callback.message.edit_text(
        text=(
            PAYMENT_METHODS_TEXT
            if invoice.payment_methods
            else "Оплата временно недоступна"
        ),
        reply_markup=keyboards.payment_methods(
            stars_price=invoice.prices[0].amount,
            rub_amount=invoice.rub_amount,
            payment_methods=invoice.payment_methods,
            priority_payment_methods=invoice.priority_payment_methods,
        ),
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


@router.callback_query(F.data == "pay_crypto")
async def process_pay_crypto(callback: CallbackQuery, deps: Dependencies) -> None:
    await show_crypto_invoice(
        callback=callback,
        deps=deps,
        purchase_kind="subscription",
        back_callback="show_mtproxy_menu",
    )


@router.callback_query(F.data == "pay_platega_sbp")
async def process_pay_platega_sbp(
    callback: CallbackQuery,
    deps: Dependencies,
) -> None:
    await show_platega_invoice(
        callback=callback,
        deps=deps,
        purchase_kind="subscription",
        back_callback="show_mtproxy_menu",
    )


@router.callback_query(F.data == "gift_certificate")
async def process_gift_certificate(callback: CallbackQuery, deps: Dependencies):
    await callback.answer()
    invoice = await deps.payments.get_stars_invoice()
    await callback.message.edit_text(
        text=(
            GIFT_CERTIFICATE_TEXT
            if invoice.payment_methods
            else "Оплата временно недоступна"
        ),
        reply_markup=keyboards.gift_certificate_payment_methods(
            stars_price=invoice.prices[0].amount,
            rub_amount=invoice.rub_amount,
            payment_methods=invoice.payment_methods,
            priority_payment_methods=invoice.priority_payment_methods,
        ),
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


@router.callback_query(F.data == "gift_crypto")
async def process_gift_crypto(callback: CallbackQuery, deps: Dependencies) -> None:
    await show_crypto_invoice(
        callback=callback,
        deps=deps,
        purchase_kind="gift_certificate",
        back_callback="show_mtproxy_menu",
    )


@router.callback_query(F.data == "gift_platega_sbp")
async def process_gift_platega_sbp(
    callback: CallbackQuery,
    deps: Dependencies,
) -> None:
    await show_platega_invoice(
        callback=callback,
        deps=deps,
        purchase_kind="gift_certificate",
        back_callback="show_mtproxy_menu",
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
                    expired_at=format_user_date(purchase.expired_at),
                    subscription_url=purchase.subscription_url,
                ),
                reply_markup=keyboards.vpn_purchased(),
            )
            return
        if payload.startswith("gift_certificate"):
            certificate = await deps.payments.confirm_gift_certificate_purchase(
                telegram_id=message.from_user.id,
                charge_id=charge_id,
                provider=provider,
            )
            if isinstance(certificate, HistoricalPurchaseReplay):
                return
            await message.answer(
                GIFT_CERTIFICATE_PURCHASED_TEXT.format(code=certificate.code)
                + render_apple_purchase_outcome(outcome=certificate.loyalty)
            )
            return
        purchase = await deps.payments.confirm_purchase(
            telegram_id=message.from_user.id,
            charge_id=charge_id,
            provider=provider,
        )
        if isinstance(purchase, HistoricalPurchaseReplay):
            return
        await message.answer(
            MTPROXY_PURCHASED_TEXT.format(
                expired_date=format_user_date(purchase.expired_date),
            )
            + render_apple_purchase_outcome(outcome=purchase.loyalty)
            + MTPROXY_PURCHASED_CTA,
            reply_markup=keyboards.key_generated(),
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
            "Пожалуйста, обратись в поддержку: @mtprotokeys_support"
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
            "Не удалось активировать сертификат. Напиши в поддержку: @mtprotokeys_support"
        )
        await message.answer(error_message)
        return
    await message.answer(
        GIFT_CERTIFICATE_ACTIVATED_TEXT.format(
            expired_date=format_user_date(result.expired_date),
        ),
        reply_markup=keyboards.key_generated(),
    )
