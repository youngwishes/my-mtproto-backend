from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import timedelta
from typing import final

from django.utils import timezone

from apps.core.exceptions import BaseServiceError
from apps.core.telegram.error_logger import log_service_error
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
                log_service_error(
                    BaseServiceError(
                        telegram_id=key.user.username,
                        message="Не удалось уведомить пользователя о завтрашнем удалении ссылки.",
                        error=str(exc),
                    )
                )


def get_notify_before_removing_daily_service() -> NotifyBeforeRemovingDailyService:
    return NotifyBeforeRemovingDailyService()
