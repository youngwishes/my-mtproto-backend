from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from apps.core.bot import TelegramBot

if TYPE_CHECKING:
    from apps.users.models import SystemUser
    from apps.vds.models import MTPRotoKey


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class NotifyPaymentService:
    """Отправляет пользователю прокси-ссылку через Telegram после оплаты."""

    def __call__(self, *, user: SystemUser, key: MTPRotoKey) -> None:
        TelegramBot.send_proxy_link(
            chat_id=user.username,
            link=key.get_proxy_link(),
        )


def get_notify_payment_service() -> NotifyPaymentService:
    return NotifyPaymentService()
