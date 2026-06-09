from __future__ import annotations

import time
from dataclasses import dataclass
from typing import final

from django.conf import settings
from django.utils import html, timezone

from apps.core.telegram.transport import send_telegram_message
from apps.notifications.selectors import get_template
from apps.vds.selectors import get_keys_expiring_on_date


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class NotifyBeforeRemovingHourBeforeService:
    def __call__(self) -> None:
        queryset = get_keys_expiring_on_date(date=timezone.now().date())
        template = get_template(slug="before_expiry_1hour")
        for key in queryset:
            try:
                message = template.render()
                send_telegram_message(chat_id=int(key.user.username), text=message.text, markup=message.markup)
                time.sleep(1)
            except Exception as exc:
                escaped_error = html.escape(str(exc))
                send_telegram_message(
                    chat_id=int(settings.MY_TELEGRAM_ID),
                    text=(
                        "🟡 <b>(BACKEND) Системное оповещение</b>\n\n"
                        "🛡 <b>Тип ошибки:</b> SERVICE (400)\n"
                        "📋 <b>Детали:</b>\n"
                        f"- Не удалось уведомить пользователя об удалении ссылки (за час до).\n"
                        f"- Пользователь — {key.user.username}\n\n"
                        f"<code>{escaped_error}</code>\n\n"
                        "⚙️ <i>Возможно, требуется внимание команды</i>"
                    ),
                )


def get_notify_before_removing_hour_before_service() -> NotifyBeforeRemovingHourBeforeService:
    return NotifyBeforeRemovingHourBeforeService()
