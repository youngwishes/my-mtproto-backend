from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.types import CallbackQuery

from src import keyboards
from src.bot import bot
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
    if deps.vpn is None:
        raise RuntimeError("VPN client is not configured")

    menu = await deps.vpn.get_menu(telegram_id=str(callback.from_user.id))
    card_invoice = await deps.payments.get_vpn_card_invoice()
    stars_invoice = await deps.payments.get_vpn_stars_invoice()
    payment_methods = keyboards.vpn_payment_methods(
        card_price_kopecks=card_invoice.prices[0].amount,
        stars_price=stars_invoice.prices[0].amount,
    )
    if menu.status == "active":
        await callback.message.edit_text(
            text=VPN_ACTIVE_TEXT.format(
                expired_at=menu.expired_at,
                subscription_url=menu.subscription_url,
            ),
            reply_markup=payment_methods,
        )
        return
    if menu.status == "expired":
        await callback.message.edit_text(
            text=VPN_EXPIRED_TEXT.format(expired_at=menu.expired_at),
            reply_markup=payment_methods,
        )
        return
    await callback.message.edit_text(
        text=VPN_MENU_TEXT,
        reply_markup=payment_methods,
    )


@router.callback_query(F.data == "vpn_pay_yukassa")
async def process_vpn_pay_yukassa(callback: CallbackQuery, deps: Dependencies) -> None:
    await callback.answer()
    invoice = await deps.payments.get_vpn_card_invoice()
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        start_parameter="vpn_yukassa",
        payload="vpn_yukassa",
        **invoice.asdict(),
    )


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
