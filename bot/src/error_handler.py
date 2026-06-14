"""Global aiogram error handler.

Replaces the per-service ``log_service_error`` decorator: domain clients stay
pure and raise :class:`BaseServiceError`; notification of the user and the admin
happens here, once, at the framework boundary.
"""

from __future__ import annotations

import html
import json
from typing import TYPE_CHECKING

from src.bot import bot
from src.config import settings
from src.exceptions import BaseServiceError

if TYPE_CHECKING:
    from aiogram import Dispatcher
    from aiogram.types import ErrorEvent


async def handle_service_errors(event: ErrorEvent) -> bool:
    exc = event.exception
    if not isinstance(exc, BaseServiceError):
        return False

    if exc.telegram_id is not None:
        await bot.send_message(chat_id=exc.telegram_id, text=exc.message)

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
    )
    return True


def register_error_handler(dp: Dispatcher) -> None:
    dp.errors.register(handle_service_errors)
