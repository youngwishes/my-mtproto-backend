"""Global aiogram error handler.

Replaces the per-service ``log_service_error`` decorator: domain clients stay
pure and raise :class:`BaseServiceError`; notification of the user and the admin
happens here, once, at the framework boundary.
"""

from __future__ import annotations

import html
import json
from typing import TYPE_CHECKING

from aiogram import F

from src import keyboards
from src.bot import bot
from src.config import settings
from src.exceptions import BaseServiceError

if TYPE_CHECKING:
    from aiogram import Dispatcher
    from aiogram.types import CallbackQuery, ErrorEvent


async def handle_service_errors(event: ErrorEvent) -> bool:
    exc = event.exception
    if not isinstance(exc, BaseServiceError):
        return False

    if exc.telegram_id is not None:
        callback_query = event.update.callback_query
        reply_markup = None
        if callback_query is not None and callback_query.data in {
            "update_link_confirm",
            "vpn_reissue_confirm",
        }:
            reply_markup = keyboards.reissue_error_notification()
        await bot.send_message(
            chat_id=exc.telegram_id,
            text=exc.message,
            reply_markup=reply_markup,
        )

    status_code = exc.context.get("status_code")
    if status_code is not None and 400 <= status_code < 500:
        return True

    pretty_error = html.escape(
        json.dumps(exc.to_dict(), indent=2, ensure_ascii=False)
    )
    await bot.send_message(
        chat_id=settings.my_telegram_id,
        text=(
            "🟡 <b>(BOT) Системное оповещение</b>\n\n"
            "🛡 <b>Тип ошибки:</b> SERVICE\n"
            "📋 <b>Детали:</b>\n"
            f"<code>{pretty_error}</code>\n\n"
            "⚙️ <i>Требуется внимание команды</i>"
        ),
        premium_emoji=False,
    )
    return True


async def dismiss_error_notification(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.delete()


def register_error_handler(dp: Dispatcher) -> None:
    dp.errors.register(handle_service_errors)
    dp.callback_query.register(
        dismiss_error_notification,
        F.data == keyboards.DISMISS_ERROR_NOTIFICATION_CALLBACK,
    )
