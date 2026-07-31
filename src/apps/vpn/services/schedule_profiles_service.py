from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, TYPE_CHECKING, final

from apps.vpn.selectors import get_active_vpn_instances, get_active_vpn_subscriptions

if TYPE_CHECKING:
    from apps.vpn.models import VPNInstance, VPNSubscription


EnqueueProfileDelivery = Callable[..., None]
GetActiveInstances = Callable[[], Iterable["VPNInstance"]]
GetActiveSubscriptions = Callable[[], Iterable["VPNSubscription"]]


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ScheduleProfilesService:
    """Ставит idempotent delivery PUT-задачи, не выполняя HTTP синхронно."""

    get_active_instances: GetActiveInstances
    get_active_subscriptions: GetActiveSubscriptions
    enqueue_delivery: EnqueueProfileDelivery

    def __call__(self, *, subscription_id: int) -> None:
        for instance in self.get_active_instances():
            self.enqueue_delivery(
                subscription_id=subscription_id,
                instance_id=instance.pk,
                operation="put",
            )

    def backfill(self, *, instance_id: int) -> None:
        for subscription in self.get_active_subscriptions():
            self.enqueue_delivery(
                subscription_id=subscription.pk,
                instance_id=instance_id,
                operation="put",
            )


def get_schedule_profiles_service() -> ScheduleProfilesService:
    from apps.vpn.tasks import deliver_vpn_profile_task

    return ScheduleProfilesService(
        get_active_instances=get_active_vpn_instances,
        get_active_subscriptions=get_active_vpn_subscriptions,
        enqueue_delivery=deliver_vpn_profile_task.delay,
    )
