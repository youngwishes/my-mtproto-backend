import html
import json
from collections.abc import Callable
from typing import Any

from bot import bot
from config import MY_TELEGRAM_ID
from exceptions import BaseServiceError


def log_service_error(__call__: Callable) -> Callable:
    async def wrapped(self, **kwargs) -> Any:
        try:
            return await __call__(self, **kwargs)
        except BaseServiceError as exc:
            await bot.send_message(
                chat_id=exc.telegram_id,
                text=exc.message,
            )
            pretty_error = json.dumps(exc.to_dict(), indent=2, ensure_ascii=False)
            escaped_error = html.escape(pretty_error)
            await bot.send_message(
                chat_id=MY_TELEGRAM_ID,
                text=(
                    "🟡 <b>(BOT) Системное оповещение</b>\n\n"
                    "🛡 <b>Тип ошибки:</b> SERVICE\n"
                    "📋 <b>Детали:</b>\n"
                    f"<code>{escaped_error}</code>\n\n"
                    "⚙️ <i>Требуется внимание команды</i>"
                ),
                parse_mode="HTML",
            )
            raise exc

    return wrapped
