from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING, Callable, Iterable, Literal, final

from django.utils import timezone

from apps.core.telegram.transport import send_telegram_message
from apps.notifications.selectors import get_template
from apps.vpn.selectors import get_vpn_subscriptions_expiring_between

if TYPE_CHECKING:
    from apps.notifications.models import NotificationTemplate
    from apps.vpn.models import VPNSubscription


VPNExpiryWindow = Literal["day", "hour", "expired"]
GetSubscriptionsInWindow = Callable[..., Iterable["VPNSubscription"]]
GetTemplate = Callable[..., "NotificationTemplate"]
SendTelegramMessage = Callable[..., None]

_TEMPLATE_SLUGS: dict[VPNExpiryWindow, str] = {
    "day": "vpn_before_expiry_1day",
    "hour": "vpn_before_expiry_1hour",
    "expired": "vpn_deactivated",
}


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class NotifyVPNExpiryService:
    """Отправляет отдельные VPN-уведомления в ограниченных expiry-окнах."""

    get_subscriptions_in_window: GetSubscriptionsInWindow
    get_notification_template: GetTemplate
    send_message: SendTelegramMessage

    def __call__(self, *, window: VPNExpiryWindow) -> int:
        now = timezone.now()
        starts_at, ends_at, is_active = self._window_bounds(window=window, now=now)
        template = self.get_notification_template(slug=_TEMPLATE_SLUGS[window])
        subscriptions = self.get_subscriptions_in_window(
            starts_at=starts_at,
            ends_at=ends_at,
            is_active=is_active,
        )
        sent_count = 0
        for subscription in subscriptions:
            message = template.render()
            self.send_message(
                chat_id=int(subscription.user.username),
                text=message.text,
                markup=message.markup,
            )
            sent_count += 1
        return sent_count

    @staticmethod
    def _window_bounds(
        *,
        window: VPNExpiryWindow,
        now: datetime,
    ) -> tuple[datetime, datetime, Literal[True, False]]:
        today_starts_at = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
        tomorrow_starts_at = today_starts_at + timedelta(days=1)
        if window == "day":
            return tomorrow_starts_at, tomorrow_starts_at + timedelta(days=1), True
        if window == "hour":
            return today_starts_at, tomorrow_starts_at, True
        return now - timedelta(days=1), now, False


def get_notify_vpn_expiry_service() -> NotifyVPNExpiryService:
    return NotifyVPNExpiryService(
        get_subscriptions_in_window=get_vpn_subscriptions_expiring_between,
        get_notification_template=get_template,
        send_message=send_telegram_message,
    )
