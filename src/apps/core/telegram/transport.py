from __future__ import annotations

from django.conf import settings
from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup


class _LazyBot:
    """Прокси, создающий TeleBot при первом обращении, а не при импорте модуля."""

    _instance: TeleBot | None = None

    def __getattr__(self, name: str):
        if self._instance is None:
            self._instance = TeleBot(token=settings.BOT_TOKEN)
        return getattr(self._instance, name)


bot = _LazyBot()


def send(
    chat_id: int,
    text: str,
    *,
    parse_mode: str = "HTML",
    markup: InlineKeyboardMarkup | None = None,
    timeout: int | None = None,
) -> None:
    bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=parse_mode,
        reply_markup=markup,
        timeout=timeout,
    )


def is_channel_member(telegram_id: int) -> bool:
    member = bot.get_chat_member(
        chat_id=settings.TELEGRAM_CHANNEL_ID, user_id=telegram_id,
    )
    return member.status in ["member", "administrator", "creator"]
