from __future__ import annotations

import time
from dataclasses import dataclass
from typing import final

from django.utils import timezone

from apps.core.exceptions import BaseServiceError
from apps.core.telegram.error_logger import log_service_error
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
                log_service_error(
                    BaseServiceError(
                        telegram_id=key.user.username,
                        message="Не удалось уведомить пользователя об удалении ссылки (за час до).",
                        error=str(exc),
                    )
                )


def get_notify_before_removing_hour_before_service() -> NotifyBeforeRemovingHourBeforeService:
    return NotifyBeforeRemovingHourBeforeService()
