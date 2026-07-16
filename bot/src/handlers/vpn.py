from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

from src import keyboards
from src.bot import bot
from src.domains.vpn import VPNAccessStatus, VPNCurrency, VPNStatus
from src.messages import (
    VPN_DISABLED_TEXT,
    VPN_EXPIRED_TEXT,
    VPN_NOT_PURCHASED_TEXT,
    VPN_PREPARING_TEXT,
    VPN_READY_TEXT,
)

if TYPE_CHECKING:
    from src.dependencies import Dependencies

router = Router()


def _render_status(
    *, status: VPNStatus, sales_enabled: bool
) -> tuple[str, InlineKeyboardMarkup]:
    texts = {
        VPNAccessStatus.NOT_PURCHASED: VPN_NOT_PURCHASED_TEXT,
        VPNAccessStatus.PREPARING: VPN_PREPARING_TEXT,
        VPNAccessStatus.READY: VPN_READY_TEXT,
        VPNAccessStatus.EXPIRED: VPN_EXPIRED_TEXT,
        VPNAccessStatus.DISABLED: VPN_DISABLED_TEXT,
    }
    text = texts[status.status].format(expired_at=status.expired_at or "—")
    markup = keyboards.vpn(
        status=status.status,
        sales_enabled=sales_enabled,
        subscription_url=status.subscription_url,
    )
    return text, markup


@router.callback_query(F.data == "vpn")
async def process_vpn(callback: CallbackQuery, deps: Dependencies) -> None:
    await callback.answer()
    status = await deps.vpn.get_status(telegram_id=callback.from_user.id)
    text, markup = _render_status(
        status=status,
        sales_enabled=deps.vpn.sales_enabled,
    )
    await callback.message.edit_text(text=text, reply_markup=markup)


async def _send_invoice(
    *, callback: CallbackQuery, deps: Dependencies, currency: VPNCurrency
) -> None:
    await callback.answer()
    invoice = await deps.vpn.create_invoice(
        telegram_id=callback.from_user.id,
        currency=currency,
    )
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        start_parameter=f"vless_vpn_{currency.lower()}",
        **invoice.telegram_kwargs(),
    )


@router.callback_query(F.data == "vpn_pay_rub")
async def process_vpn_pay_rub(
    callback: CallbackQuery, deps: Dependencies
) -> None:
    await _send_invoice(callback=callback, deps=deps, currency="RUB")


@router.callback_query(F.data == "vpn_pay_stars")
async def process_vpn_pay_stars(
    callback: CallbackQuery, deps: Dependencies
) -> None:
    await _send_invoice(callback=callback, deps=deps, currency="XTR")


@router.callback_query(F.data == "vpn_reissue")
async def process_vpn_reissue(
    callback: CallbackQuery, deps: Dependencies
) -> None:
    await callback.answer()
    await deps.vpn.reissue(telegram_id=callback.from_user.id)
    status = VPNStatus(status=VPNAccessStatus.PREPARING)
    text, markup = _render_status(
        status=status,
        sales_enabled=deps.vpn.sales_enabled,
    )
    await callback.message.edit_text(text=text, reply_markup=markup)


__all__ = [
    "process_vpn",
    "process_vpn_pay_rub",
    "process_vpn_pay_stars",
    "process_vpn_reissue",
    "router",
]
