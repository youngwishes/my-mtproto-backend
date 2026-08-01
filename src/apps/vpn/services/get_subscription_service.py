from __future__ import annotations

from dataclasses import dataclass
from typing import final

from django.utils import timezone

from apps.vpn.selectors import (
    get_active_vpn_instances,
    get_vpn_subscription_by_token,
)
from apps.vpn.services.build_subscription_service import BuildSubscriptionService


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class GetSubscriptionService:
    """Возвращает HAPP-конфигурацию только для действующей VPN-подписки."""

    build_subscription: BuildSubscriptionService

    def __call__(self, *, token: str) -> str | None:
        subscription = get_vpn_subscription_by_token(token=token)
        if subscription is None:
            return None

        if not subscription.is_active or subscription.expired_at <= timezone.now():
            return self.build_subscription(subscription=subscription, instances=())

        return self.build_subscription(
            subscription=subscription,
            instances=get_active_vpn_instances(),
        )


def get_subscription_service() -> GetSubscriptionService:
    return GetSubscriptionService(build_subscription=BuildSubscriptionService())
