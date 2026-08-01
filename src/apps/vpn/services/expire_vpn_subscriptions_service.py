from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Callable, Iterable, final

from django.db import transaction

from apps.vpn.selectors import (
    get_active_vpn_instances,
    get_expired_active_vpn_subscriptions,
)

if TYPE_CHECKING:
    from apps.vpn.models import VPNInstance, VPNSubscription


GetExpiredSubscriptions = Callable[..., Iterable["VPNSubscription"]]
GetActiveInstances = Callable[[], Iterable["VPNInstance"]]
EnqueueProfileDelivery = Callable[..., None]


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ExpireVPNSubscriptionsService:
    """Деактивирует VPN-подписки и после commit ставит удаление профилей."""

    get_expired_subscriptions: GetExpiredSubscriptions
    get_active_instances: GetActiveInstances
    enqueue_delivery: EnqueueProfileDelivery

    def __call__(self, *, now: datetime) -> int:
        return self.deactivate(
            subscriptions=self.get_expired_subscriptions(now=now),
        )

    def deactivate(self, *, subscriptions: Iterable[VPNSubscription]) -> int:
        """Идемпотентно отключает переданные активные подписки."""
        active_subscriptions = tuple(
            subscription for subscription in subscriptions if subscription.is_active
        )
        if not active_subscriptions:
            return 0

        active_instance_ids = tuple(instance.pk for instance in self.get_active_instances())
        deliveries = tuple(
            (subscription.pk, instance_id)
            for subscription in active_subscriptions
            for instance_id in active_instance_ids
        )
        with transaction.atomic():
            for subscription in active_subscriptions:
                subscription.is_active = False
                subscription.save(update_fields=["is_active", "updated_at"])
            transaction.on_commit(lambda: self._enqueue_deletes(deliveries=deliveries))
        return len(active_subscriptions)

    def _enqueue_deletes(self, *, deliveries: tuple[tuple[int, int], ...]) -> None:
        for subscription_id, instance_id in deliveries:
            self.enqueue_delivery(
                subscription_id=subscription_id,
                instance_id=instance_id,
                operation="delete",
            )


def get_expire_vpn_subscriptions_service() -> ExpireVPNSubscriptionsService:
    from apps.vpn.tasks import deliver_vpn_profile_task

    return ExpireVPNSubscriptionsService(
        get_expired_subscriptions=get_expired_active_vpn_subscriptions,
        get_active_instances=get_active_vpn_instances,
        enqueue_delivery=deliver_vpn_profile_task.delay,
    )
