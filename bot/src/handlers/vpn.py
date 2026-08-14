from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.types import CallbackQuery

from src import keyboards
from src.bot import bot
from src.exceptions import VPNSubscriptionDoesNotExist
from src.handlers.payments import show_crypto_invoice, show_platega_invoice
from src.messages import (
    VPN_ACTIVE_TEXT,
    VPN_EXPIRED_TEXT,
    VPN_MENU_TEXT,
    VPN_PRODUCT_MENU_TEXT,
)

if TYPE_CHECKING:
    from src.dependencies import Dependencies

router = Router()


@router.callback_query(F.data == "show_vpn_menu")
async def process_vpn_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        text=VPN_PRODUCT_MENU_TEXT,
        reply_markup=keyboards.vpn_menu(),
    )


@router.callback_query(F.data == "vpn")
async def process_vpn(callback: CallbackQuery, deps: Dependencies) -> None:
    await callback.answer()
    stars_invoice = await deps.payments.get_vpn_stars_invoice()
    await callback.message.edit_text(
        text=(
            VPN_MENU_TEXT
            if stars_invoice.payment_methods
            else "Оплата временно недоступна"
        ),
        reply_markup=keyboards.vpn_payment_methods(
            stars_price=stars_invoice.prices[0].amount,
            rub_amount=stars_invoice.rub_amount,
            payment_methods=stars_invoice.payment_methods,
            priority_payment_methods=stars_invoice.priority_payment_methods,
        ),
    )


@router.callback_query(F.data == "vpn_subscription")
async def process_vpn_subscription(
    callback: CallbackQuery,
    deps: Dependencies,
) -> None:
    await callback.answer()
    if deps.vpn is None:
        raise RuntimeError("VPN client is not configured")

    menu = await deps.vpn.get_menu(telegram_id=str(callback.from_user.id))
    if menu.status == "none":
        raise VPNSubscriptionDoesNotExist(str(callback.from_user.id))

    if menu.status == "active":
        text = VPN_ACTIVE_TEXT.format(
            expired_at=menu.expired_at,
            subscription_url=menu.subscription_url,
        )
    else:
        text = VPN_EXPIRED_TEXT.format(
            expired_at=menu.expired_at,
            subscription_url=menu.subscription_url,
        )

    await callback.message.edit_text(
        text=text,
        reply_markup=keyboards.vpn_subscription(
            is_expired=menu.status == "expired",
        ),
    )


@router.callback_query(F.data == "vpn_pay_yukassa")
async def process_vpn_pay_yukassa(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "vpn_pay_stars")
async def process_vpn_pay_stars(callback: CallbackQuery, deps: Dependencies) -> None:
    await callback.answer()
    invoice = await deps.payments.get_vpn_stars_invoice()
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=invoice.title,
        description=invoice.description,
        start_parameter="vpn_stars",
        payload="vpn_stars",
        currency=invoice.currency,
        prices=invoice.prices,
        provider_token=invoice.provider_token,
    )


@router.callback_query(F.data == "vpn_pay_crypto")
async def process_vpn_pay_crypto(
    callback: CallbackQuery,
    deps: Dependencies,
) -> None:
    await show_crypto_invoice(
        callback=callback,
        deps=deps,
        purchase_kind="vpn_subscription",
        back_callback="show_vpn_menu",
    )


@router.callback_query(F.data == "vpn_pay_platega_sbp")
async def process_vpn_pay_platega_sbp(
    callback: CallbackQuery,
    deps: Dependencies,
) -> None:
    await show_platega_invoice(
        callback=callback,
        deps=deps,
        purchase_kind="vpn_subscription",
        back_callback="show_vpn_menu",
    )
