from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import final

from django.db import transaction
from apps.vpn.enums import VPNAccessState
from apps.vpn.models import VPNAccess
from apps.vpn.selectors import (
    get_vpn_access_for_delivery,
    has_eligible_exact_vpn_apply,
    publish_vpn_access_conditionally,
)


def _register_after_commit(callback: Callable[[], None]) -> None:
    transaction.on_commit(callback, robust=True)


def _noop_schedule_notification(*, access_id: int, revision: int) -> None:
    """Periodic recovery remains authoritative when no accelerator is wired."""


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class PublishVPNReadinessService:
    get_access: Callable[..., VPNAccess | None]
    has_eligible_apply: Callable[..., bool]
    publish_conditionally: Callable[..., bool]
    register_after_commit: Callable[[Callable[[], None]], None]
    schedule_notification: Callable[..., None]

    def __call__(self, *, access_id: int) -> bool:
        with transaction.atomic():
            access = self.get_access(access_id=access_id)
            if (
                access is None
                or access.state != VPNAccessState.PREPARING
                or not self.has_eligible_apply(access=access)
                or not self.publish_conditionally(access=access)
            ):
                return False
            self.register_after_commit(
                partial(
                    self.schedule_notification,
                    access_id=access.pk,
                    revision=access.desired_revision,
                )
            )
            return True


def get_publish_vpn_readiness_service(
    *, schedule_notification: Callable[..., None] = _noop_schedule_notification
) -> PublishVPNReadinessService:
    return PublishVPNReadinessService(
        get_access=get_vpn_access_for_delivery,
        has_eligible_apply=has_eligible_exact_vpn_apply,
        publish_conditionally=publish_vpn_access_conditionally,
        register_after_commit=_register_after_commit,
        schedule_notification=schedule_notification,
    )
