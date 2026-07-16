from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import final

from django.db import transaction
from django.utils import timezone
from apps.vpn.enums import VPNAccessState
from apps.vpn.models import VPNAccess
from apps.vpn.selectors import (
    get_vpn_access_for_delivery,
    has_eligible_exact_vpn_apply,
    publish_vpn_access_conditionally,
    deactivate_superseded_vpn_applies,
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
    mark_receipt_ready: Callable[..., bool]
    now: Callable[[], datetime]
    deactivate_superseded: Callable[..., None] = deactivate_superseded_vpn_applies

    def __call__(self, *, access_id: int) -> bool:
        with transaction.atomic():
            access = self.get_access(access_id=access_id)
            ready_at = self.now()
            if (
                access is None
                or access.state != VPNAccessState.PREPARING
                or not self.has_eligible_apply(access=access)
                or not self.publish_conditionally(access=access, now=ready_at)
            ):
                return False
            self.mark_receipt_ready(access_id=access.pk, ready_at=ready_at)
            self.deactivate_superseded(access=access)
            self.register_after_commit(
                partial(
                    self.schedule_notification,
                    access_id=access.pk,
                    revision=access.desired_revision,
                )
            )
            return True


def get_publish_vpn_readiness_service(
    *,
    schedule_notification: Callable[..., None] = _noop_schedule_notification,
    mark_receipt_ready: Callable[..., bool] | None = None,
) -> PublishVPNReadinessService:
    if mark_receipt_ready is None:
        from apps.payments.selectors import mark_latest_vpn_receipt_ready

        mark_receipt_ready = mark_latest_vpn_receipt_ready
    return PublishVPNReadinessService(
        get_access=get_vpn_access_for_delivery,
        has_eligible_apply=has_eligible_exact_vpn_apply,
        publish_conditionally=publish_vpn_access_conditionally,
        register_after_commit=_register_after_commit,
        schedule_notification=schedule_notification,
        mark_receipt_ready=mark_receipt_ready,
        now=timezone.now,
    )
