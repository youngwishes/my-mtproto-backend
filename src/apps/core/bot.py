from __future__ import annotations

import html
import json
from collections.abc import Callable
from typing import TYPE_CHECKING

from django.conf import settings
from rest_framework.exceptions import ValidationError
from telebot import TeleBot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

if TYPE_CHECKING:
    from apps.core.service import BaseServiceError, BaseInfraError

bot = TeleBot(token=settings.TELEGRAM_BOT_TOKEN)


class TelegramBot:
    @classmethod
    def update_user_link_notification(cls, telegram_id: int) -> None:
        text = (
            "✨ <b>Привет!</b>\n\n"
            "⚡️ Мы доработали функционал нашего бота, и теперь ссылку <b>можно перевыпустить</b>, если она перестала работать. \n\n"
            "👀 Срок действия ссылки также остается <b>тем же, что был у старой.</b>\n\n"
            "⚠️ Помни, что после перевыпуска ссылки, старая <b>уже никогда не заработает.</b> Используй ту, что тебе выдаст бот.\n\n"
            "👇 <b>Попробуй перевыпустить:</b>"
        )
        try:
            bot.send_message(
                text=text,
                chat_id=telegram_id,
                reply_markup=InlineKeyboardMarkup(
                    keyboard=[
                        [
                            InlineKeyboardButton(
                                text="⚡️ Перевыпустить ссылку",
                                callback_data="update_link",
                            )
                        ]
                    ]
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass

    @classmethod
    def send_invite_to_chat(cls, telegram_id: int) -> None:
        bot.send_message(
            text=(
                "👋 Привет!\n\n"
                "😎 Вижу, ты неплохо пользуешься нашим сервисом, и я этому <b>очень рад!</b>\n"
                "🎁 Недавно мы запустили реферальную программу — "
                "благодаря ей можно пользоваться ключами <b>бесплатно ещё 2 недели.</b>\n\n"
                "📢 Все самые горячие новости и акции — в нашем канале.\n\n"
                "Подписывайся, чтобы быть в курсе 👇"
            ),
            chat_id=telegram_id,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                keyboard=[
                    [
                        InlineKeyboardButton(
                            text="⚡️ Перейти на канал",
                            url="https://t.me/mtproto_keys"
                        )
                    ]
                ]
            ),
        )

    @classmethod
    def send_invite_to_chat_v2(cls, telegram_id: int) -> None:
        bot.send_message(
            text=(
                "👋 <b>Привет!</b>\n\n"
                "⚡️Недавно я выкатил большой конкурс, "
                "благодаря которому у тебя есть возможность получить ссылку <b>НА-ВСЕ-ГДА.</b>\n\n"
                "📢 За всеми новостями и акциями следи в моем канале.\n"
                "👇 Пожалуйста, подпишись, <b>я там пишу редко, но по делу.</b>"
            ),
            chat_id=telegram_id,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🎁 Что за конкурс?",
                            url="https://t.me/mtproto_keys/42"
                        )
                    ]
                ]
            ),
        )

    @classmethod
    def notify_before_removing(cls, chat_id: str) -> None:
        bot.send_message(
            chat_id=chat_id,
            text=(
                "⚠️ <b>Внимание! Остался всего 1 день</b>\n\n"
                "Привет! Твоя ссылка для ускорения <b>MTPRoto</b> перестанет работать уже <b>завтра</b>.\n\n"
                "После этого Telegram снова станет медленным: фото будут грузиться минутами, а видео зависать. Не хочешь возвращаться к этому? 😉\n\n"
                "👇 <b>Продли доступ сейчас — это займет 10 секунд:</b>"
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                keyboard=[
                    [
                        InlineKeyboardButton(
                            text="⚡️ ПРОДЛИТЬ ЗА 79 ₽",
                            callback_data="boost_paid",
                        )
                    ]
                ]
            ),
        )

    @classmethod
    def send_message(cls, chat_id: str, text: str) -> None:
        bot.send_message(
            chat_id=chat_id,
            text=text,
        )

    @classmethod
    def send_message_deactivate_link(cls, chat_id: str) -> None:
        bot.send_message(
            chat_id=chat_id,
            text=(
                "👋 Привет!\n\n"
                "Срок действия твоей ссылки подошел к концу, и теперь Telegram может работать медленнее.\n\n"
                "<b>Но есть отличная новость:</b> ты можешь легко вернуть скорость обратно!\n\n"
                "👉 <b>Для этого нажми на кнопку ниже:</b>"
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🚀 ВЕРНУТЬ СКОРОСТЬ (79 RUB)",
                            callback_data="boost_paid",
                        )
                    ]
                ]
            ),
        )

    @classmethod
    def send_message_with_link(cls, *, chat_id: str, link: str, text: str) -> None:
        try:
            bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                timeout=settings.TELEGRAM_TIMEOUT,
                reply_markup=InlineKeyboardMarkup(
                    keyboard=[
                        [
                            InlineKeyboardButton(
                                text="🚀 Подключиться",
                                url=link,
                            )
                        ]
                    ]
                ),
            )
        except Exception:
            pass

    @classmethod
    def send_proxy_link(cls, *, chat_id: int | str, link: str) -> None:
        bot.send_message(
            chat_id=chat_id,
            text=(
                "🎉 *Спасибо за покупку!*\n\n"
                "✨ Ваш VPN-ключ готов к использованию.\n"
                "👉 Нажмите кнопку *«Подключиться»* ниже.\n\n"
                "⏳ *Важно:* ссылка действует **30 дней** с момента покупки.\n"
                "🗓 После этого срока доступ потребуется продлить."
            ),
            parse_mode="Markdown",
            timeout=settings.TELEGRAM_TIMEOUT,
            reply_markup=InlineKeyboardMarkup(
                keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🚀 Подключиться",
                            url=link,
                        )
                    ]
                ]
            ),
        )

    @classmethod
    def log_infra_error(cls, exc: BaseInfraError) -> None:
        error_dict = exc.to_dict()

        pretty_error = json.dumps(error_dict, indent=2, ensure_ascii=False)
        escaped_error = html.escape(pretty_error)
        bot.send_message(
            chat_id=settings.MY_TELEGRAM_ID,
            text=(
                "🔴 <b>(BACKEND) Системное оповещение</b>\n\n"
                "🛡 <b>Тип ошибки:</b> SERVER INTERNAL ERROR (500)\n"
                "📋 <b>Детали:</b>\n"
                f"<code>{escaped_error}</code>\n\n"
                "⚙️ <i>Требуется СРОЧНОЕ внимание команды</i>"
            ),
            parse_mode="HTML",
            timeout=settings.TELEGRAM_TIMEOUT,
        )

    @classmethod
    def log_service_error(cls, exc: BaseServiceError) -> None:
        error_dict = exc.to_dict()

        pretty_error = json.dumps(error_dict, indent=2, ensure_ascii=False)
        escaped_error = html.escape(pretty_error)
        bot.send_message(
            chat_id=settings.MY_TELEGRAM_ID,
            text=(
                "🟡 <b>(BACKEND) Системное оповещение</b>\n\n"
                "🛡 <b>Тип ошибки:</b> SERVICE (400)\n"
                "📋 <b>Детали:</b>\n"
                f"<code>{escaped_error}</code>\n\n"
                "⚙️ <i>Возможно, требуется внимание команды</i>"
            ),
            parse_mode="HTML",
            timeout=settings.TELEGRAM_TIMEOUT,
        )

    @classmethod
    def log_bad_request(cls, request: dict, response: Exception, url: str) -> None:
        bot.send_message(
            chat_id=settings.MY_TELEGRAM_ID,
            text=(
                f"🔥 <b>400 — BAD REQUEST</b>\n\n"
                f"<b>Url:</b>\n<pre>{url}</pre>\n\n"
                f"<b>Request:</b>\n<pre>{request}</pre>\n\n"
                f"<b>Response:</b>\n<pre>{response}</pre>"
            ),
            parse_mode="HTML",
            timeout=settings.TELEGRAM_TIMEOUT,
        )

    @classmethod
    def send_sorry(cls, exc: BaseInfraError | BaseServiceError) -> None:
        bot.send_message(
            chat_id=exc.telegram_id,
            text=(
                "✨ <b>Уважаемый клиент</b>\n\n"
                "К сожалению, в данный момент наши серверы испытывают "
                "<b>повышенные нагрузки</b>. Наши инженеры уже занимаются "
                "решением вопроса, чтобы восстановить работу в кратчайшие сроки.\n\n"
                "Мы ценим ваше терпение и понимание. Если вы только что приобрели"
                " ключ, чтобы не заставлять вас ждать, "
                "пожалуйста, <b>направьте это сообщение в поддержку</b> — вам "
                "оперативно предоставят доступ в ручном режиме.\n\n"
                "📩 <b>Поддержка:</b> @mtproto_keys\n\n"
                "<i>С уважением, команда сервиса</i>"
            ),
            parse_mode="HTML",
        )

    @classmethod
    def is_channel_member(cls, telegram_id: int) -> bool:
        member = bot.get_chat_member(
            chat_id=settings.TELEGRAM_CHANNEL_ID, user_id=telegram_id
        )
        return member.status in ["member", "administrator", "creator"]


def notify_bad_request(view: Callable) -> Callable:
    def _wrapped(self, *args, **kwargs) -> Callable:
        try:
            return view(self, *args, **kwargs)
        except ValidationError as exc:
            request = getattr(self, "request", None)
            data = dict(getattr(request, "data", None))
            TelegramBot.log_bad_request(
                request=data,
                response=exc,
                url=getattr(request, "path", None),
            )

        return view(self, *args, **kwargs)

    return _wrapped
