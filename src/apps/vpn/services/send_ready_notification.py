from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from django.conf import settings
from apps.vpn.enums import VPNAccessState
from apps.vpn.models import VPNAccess
from apps.vpn.selectors import (
    get_vpn_access_for_delivery,
    mark_vpn_ready_notification_sent,
)

if TYPE_CHECKING:
    from apps.core.bot import TelegramBot


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class SendVPNReadyNotificationService:
    get_access: Callable[..., VPNAccess | None]
    bot: TelegramBot
    mark_notified: Callable[..., bool]
    subscription_base_url: str

    def __call__(self, *, access_id: int, revision: int) -> bool:
        access = self.get_access(access_id=access_id)
        if (
            access is None
            or access.state != VPNAccessState.READY
            or access.published_revision != revision
            or access.ready_notification_revision >= revision
        ):
            return False
        url = f"{self.subscription_base_url.rstrip('/')}/{access.subscription_token}/"
        self.bot.send_message(
            chat_id=int(access.user.username),
            text=(
                "✅ <b>VPN-доступ готов</b>\n\n"
                "Добавьте эту стабильную ссылку подписки в VPN-клиент:\n"
                f"{url}"
            ),
        )
        return self.mark_notified(access_id=access.pk, revision=revision)


def get_send_vpn_ready_notification_service() -> SendVPNReadyNotificationService:
    from apps.core.bot import TelegramBot

    return SendVPNReadyNotificationService(
        get_access=get_vpn_access_for_delivery,
        bot=TelegramBot(),
        mark_notified=mark_vpn_ready_notification_sent,
        subscription_base_url=settings.VPN_SUBSCRIPTION_BASE_URL,
    )
