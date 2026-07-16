from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from django.db import OperationalError
from django.utils import timezone

from apps.vpn.exceptions import VPNRefundConflict
from apps.vpn.selectors import deactivate_vpn_refund_conditionally

if TYPE_CHECKING:
    from apps.users.models import SystemUser
    from apps.vpn.models import VPNPurchase


def _schedule_reconcile() -> None:
    from apps.vpn.tasks import reconcile_vpn_nodes_task

    reconcile_vpn_nodes_task.delay()


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class DeactivateVPNRefundService:
    schedule_reconcile: Callable[[], None]
    deactivate_conditionally: Callable[..., bool] = deactivate_vpn_refund_conditionally

    def __call__(
        self, *, purchase: VPNPurchase, actor: SystemUser, reason: str
    ) -> bool:
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ValueError("refund reason is required")
        try:
            changed = self.deactivate_conditionally(
                purchase=purchase,
                actor_id=actor.pk,
                reason=normalized_reason,
                now=timezone.now(),
            )
        except OperationalError as exc:
            raise VPNRefundConflict() from exc
        if changed:
            try:
                self.schedule_reconcile()
            except Exception:
                pass
        return changed


def get_deactivate_vpn_refund_service() -> DeactivateVPNRefundService:
    return DeactivateVPNRefundService(schedule_reconcile=_schedule_reconcile)
