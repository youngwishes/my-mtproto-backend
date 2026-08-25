from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from django.conf import settings
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

from apps.core.telegram.transport import send_telegram_message
from apps.notifications.selectors import get_mtproto_link_reissue_recipients

if TYPE_CHECKING:
    from apps.users.models import SystemUser


_MESSAGE_TEXT = (
    "⚠️ <b>Пожалуйста, обновите ссылки MTProxy</b>\n\n"
    "Мы обновили настройки подключения, чтобы сохранить стабильную работу "
    "сервиса.\n\n"
    "Нажмите кнопку ниже и подтвердите перевыпуск. После этого добавьте новые "
    "ссылки в Telegram, а старые можно удалить.\n\n"
    "Это займёт меньше минуты."
)
_MESSAGE_MARKUP = InlineKeyboardMarkup(
    keyboard=[
        [
            InlineKeyboardButton(
                text="🔄 Перевыпустить ссылки",
                callback_data="update_link",
            )
        ]
    ]
)


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class NotifyMTPRotoLinkReissueService:
    get_recipients: Callable[[], Iterable[SystemUser]]
    send_message: Callable[..., None]
    sleep: Callable[[float], None]
    admin_telegram_id: int

    def __call__(self, *, preview: bool = True) -> None:
        if preview:
            self.send_message(
                chat_id=self.admin_telegram_id,
                text=_MESSAGE_TEXT,
                markup=_MESSAGE_MARKUP,
            )
            return

        sent_count = 0
        for index, user in enumerate(self.get_recipients()):
            if index > 0:
                self.sleep(0.5)
            try:
                self.send_message(
                    chat_id=int(user.username),
                    text=_MESSAGE_TEXT,
                    markup=_MESSAGE_MARKUP,
                )
            except Exception:
                continue
            sent_count += 1

        self.send_message(
            chat_id=self.admin_telegram_id,
            text=f"Рассылка завершена. Уведомлено пользователей: {sent_count}",
        )


def get_notify_mtproto_link_reissue_service() -> NotifyMTPRotoLinkReissueService:
    return NotifyMTPRotoLinkReissueService(
        get_recipients=get_mtproto_link_reissue_recipients,
        send_message=send_telegram_message,
        sleep=time.sleep,
        admin_telegram_id=int(settings.MY_TELEGRAM_ID),
    )
