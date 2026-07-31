from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import QuerySet
from django.utils import timezone

from apps.vpn.models import VPNInstance, VPNSubscription

if TYPE_CHECKING:
    from apps.users.models import SystemUser


def get_active_vpn_instances() -> QuerySet[VPNInstance]:
    """Активные VPN-ноды в порядке выдачи профилей."""
    return VPNInstance.objects.active().order_by("number", "pk")


def get_active_vpn_subscription(*, user: SystemUser) -> VPNSubscription | None:
    """Рабочая VPN-подписка пользователя."""
    return VPNSubscription.objects.active().filter(
        user=user,
        expired_at__gt=timezone.now(),
    ).first()


def get_vpn_subscription_by_token(*, token: str) -> VPNSubscription | None:
    """VPN-подписка по постоянному токену, включая неактивные и истёкшие."""
    return VPNSubscription.objects.filter(token=token).first()
