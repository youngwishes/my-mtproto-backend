from __future__ import annotations

import time
from dataclasses import dataclass
from typing import final

from django.utils import timezone

from apps.core.exceptions import BaseServiceError
from apps.core.telegram.error_logger import log_service_error
from apps.core.telegram.transport import send_telegram_message
from apps.notifications.selectors import get_template
from apps.vds.selectors import get_all_active_vds_instances, get_keys_expired_up_to_date
from apps.vds.services.remove_key_infra_service import get_remove_user_key_infra_service


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class RemoveExpiredKeysDailyService:
    def __call__(self) -> None:
        queryset = get_keys_expired_up_to_date(date=timezone.now().date())
        usernames = list(queryset.values_list("user__username", flat=True))
        if not usernames:
            return

        service = get_remove_user_key_infra_service()
        for server in get_all_active_vds_instances():
            service(server=server, keys=queryset)

        queryset.update(is_active=False, was_deleted=True)

        template = get_template(slug="link_deactivated")
        for username in usernames:
            try:
                message = template.render()
                send_telegram_message(chat_id=int(username), text=message.text, markup=message.markup)
                time.sleep(0.5)
            except Exception as exc:
                log_service_error(
                    BaseServiceError(
                        telegram_id=username,
                        message="Не удалось уведомить пользователя об удалении ссылки",
                        error=str(exc),
                    )
                )


def get_remove_expired_keys_daily_service() -> RemoveExpiredKeysDailyService:
    return RemoveExpiredKeysDailyService()
