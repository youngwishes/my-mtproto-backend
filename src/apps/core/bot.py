from django.conf import settings
from telebot import TeleBot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

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
