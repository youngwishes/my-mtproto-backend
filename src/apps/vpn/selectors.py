from __future__ import annotations

from datetime import datetime
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


def get_active_vpn_subscriptions() -> QuerySet[VPNSubscription]:
    """Рабочие VPN-подписки для delivery и bootstrap node-agent."""
    return VPNSubscription.objects.active().filter(expired_at__gt=timezone.now())


def get_vpn_subscription_for_update(*, user_id: int) -> VPNSubscription | None:
    """Подписка пользователя с блокировкой, включая истёкшие и неактивные."""
    return VPNSubscription.objects.select_for_update().filter(user_id=user_id).first()


def get_vpn_subscription_by_user_id(*, user_id: int) -> VPNSubscription | None:
    """Подписка пользователя без блокировки для recovery после отката транзакции."""
    return VPNSubscription.objects.filter(user_id=user_id).first()


def get_vpn_subscription_by_id(*, subscription_id: int) -> VPNSubscription | None:
    """VPN-подписка по ID для асинхронной delivery-задачи."""
    return VPNSubscription.objects.select_related("user").filter(pk=subscription_id).first()


def get_vpn_instance_by_id(*, instance_id: int) -> VPNInstance | None:
    """VPN-нода по ID для асинхронной delivery-задачи."""
    return VPNInstance.objects.filter(pk=instance_id).first()


def create_vpn_subscription(
    *,
    user: SystemUser,
    expired_at: datetime,
) -> VPNSubscription:
    """Создаёт первую VPN-подписку с постоянными credentials модели."""
    return VPNSubscription.objects.create(user=user, expired_at=expired_at)


def get_vpn_subscription_by_token(*, token: str) -> VPNSubscription | None:
    """VPN-подписка по постоянному токену, включая неактивные и истёкшие."""
    return VPNSubscription.objects.filter(token=token).first()
