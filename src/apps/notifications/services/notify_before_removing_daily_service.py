from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import timedelta
from typing import final

from django.conf import settings
from django.utils import html, timezone

from apps.core.telegram.transport import send_telegram_message
from apps.notifications.selectors import get_template
from apps.vds.selectors import get_unnotified_keys_expiring_on_date


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class NotifyBeforeRemovingDailyService:
    def __call__(self) -> None:
        target_date = (timezone.now() + timedelta(days=1)).date()
        queryset = get_unnotified_keys_expiring_on_date(date=target_date)

        template = get_template(slug="before_expiry_1day")
        for key in queryset:
            try:
                message = template.render()
                send_telegram_message(chat_id=int(key.user.username), text=message.text, markup=message.markup)
                key.user_notified = True
                key.save(update_fields=["user_notified"])
                time.sleep(0.5)
            except Exception as exc:
                escaped_error = html.escape(str(exc))
                send_telegram_message(
                    chat_id=int(settings.MY_TELEGRAM_ID),
                    text=(
                        "🟡 <b>(BACKEND) Системное оповещение</b>\n\n"
                        "🛡 <b>Тип ошибки:</b> SERVICE (400)\n"
                        "📋 <b>Детали:</b>\n"
                        f"- Не удалось уведомить пользователя о завтрашнем удалении ссылки.\n"
                        f"- Пользователь — {key.user.username}\n\n"
                        f"<code>{escaped_error}</code>\n\n"
                        "⚙️ <i>Возможно, требуется внимание команды</i>"
                    ),
                )


def get_notify_before_removing_daily_service() -> NotifyBeforeRemovingDailyService:
    return NotifyBeforeRemovingDailyService()
