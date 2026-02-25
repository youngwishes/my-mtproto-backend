from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from telebot import TeleBot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

if TYPE_CHECKING:
    from apps.core.service import BaseServiceError

bot = TeleBot(token=settings.TELEGRAM_BOT_TOKEN)


class TelegramBot:
    def send_proxy_link(self, *, chat_id: int | str, link: str) -> None:
        bot.send_message(
            chat_id=chat_id,
            text=(
                "Спасибо за покупку!\n"
                "Чтобы подключиться к VPN — нажмите на кнопку под сообщением.\n"
                "Ссылка будет действовать 30 дней, после чего станет неактивной."
            ),
            reply_markup=InlineKeyboardMarkup(
                keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Подключиться",
                            url=link,
                        )
                    ]
                ]
            ),
        )

    @classmethod
    def log_error(cls, exc: BaseServiceError) -> None:
        bot.send_message(
            chat_id=1487189460,
            text=f"🔥🔥🔥 Ошибка на сервере:\n\n```json\n{exc.to_dict()}```",
            parse_mode="MarkdownV2"
        )

    @classmethod
    def send_sorry(cls, exc: BaseServiceError) -> None:
        bot.send_message(
            chat_id=exc.telegram_id,
            text=(
                "💀 Упс, кажется, наши сервера <b>перегружены</b>.\n\n"
                "Сильно просим прощения за доставленные неудобства.\n"
                "Пожалуйста, <b>перешлите данное сообщение в поддержку.</b> "
                "Вам выдадут ссылку на подключение в ручном режиме.\n\n"
                "🤝 <i>Связь через личные сообщения канала:\n@mtproto_keys.</i>"
            ),
            parse_mode="HTML"
        )
