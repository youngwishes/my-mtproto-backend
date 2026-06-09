from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import timedelta
from typing import final

from django.conf import settings
from django.utils import html

from apps.core.telegram.transport import send_telegram_message
from apps.vds.selectors import get_active_broadcast_keys


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class BroadcastProxyLinksService:
    def __call__(self, *, testing: bool = False) -> None:
        from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

        keys = get_active_broadcast_keys(testing=testing)

        sent_count = 0
        for key in keys:
            try:
                send_telegram_message(
                    chat_id=int(key.user.username),
                    text=(
                        "✨ <b>Привет!</b>\n\n"
                        "В последнее время часть ссылок могла работать нестабильно из-за блокировок. "
                        "Мы долго работали над решением — и нам удалось <b>полностью обойти ограничения.</b>\n\n"
                        "Сейчас всё работает стабильно, и мы решили продлить твою ссылку на <b>3 дня</b> "
                        "в качестве компенсации за неудобства.\n\n"
                        f"👇 <b>Твоя ссылка (действует до {(key.expired_date + timedelta(days=3)).strftime('%d.%m.%Y')}):</b>"
                    ),
                    markup=InlineKeyboardMarkup(
                        keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="🇳🇱 Подключиться",
                                    url=key.get_proxy_link(),
                                )
                            ]
                        ]
                    ),
                )
                key.expired_date = key.expired_date + timedelta(days=3)
                key.save(update_fields=["expired_date"])
                sent_count += 1
                if sent_count % 10 == 0:
                    time.sleep(1)
            except Exception as exc:
                try:
                    escaped_error = html.escape(str(exc))
                    send_telegram_message(
                        chat_id=int(settings.MY_TELEGRAM_ID),
                        text=(
                            "🟡 <b>(BACKEND) Системное оповещение</b>\n\n"
                            "🛡 <b>Тип ошибки:</b> SERVICE (400)\n"
                            "📋 <b>Детали:</b>\n"
                            f"- Не удалось отправить broadcast пользователю\n"
                            f"- Пользователь — {key.user.username}\n\n"
                            f"<code>{escaped_error}</code>\n\n"
                            "⚙️ <i>Возможно, требуется внимание команды</i>"
                        ),
                    )
                except Exception:
                    pass


def get_broadcast_proxy_links_service() -> BroadcastProxyLinksService:
    return BroadcastProxyLinksService()
