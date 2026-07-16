from __future__ import annotations

from typing import Any

from apps.core.telegram.transport import send_telegram_message


class TelegramBot:
    """Small injectable facade over the process-wide Telegram transport."""

    def send_message(self, *, chat_id: int, text: str, **kwargs: Any) -> None:
        send_telegram_message(chat_id=chat_id, text=text, **kwargs)


__all__ = ["TelegramBot"]
