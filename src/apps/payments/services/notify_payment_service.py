from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from apps.core.service import log_service_error
from apps.notifications.services.send_notification_service import SendNotificationService

if TYPE_CHECKING:
    from apps.users.models import SystemUser
    from apps.vds.models import MTPRotoKey


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class NotifyPaymentService:
    """Отправляет пользователю прокси-ссылку через Telegram после оплаты."""

    @log_service_error
    def __call__(self, *, user: SystemUser, key: MTPRotoKey) -> None:
        SendNotificationService(
            slug="proxy_purchased",
            context={"link": key.get_proxy_link()},
        )(chat_id=int(user.username))


def get_notify_payment_service() -> NotifyPaymentService:
    return NotifyPaymentService()
