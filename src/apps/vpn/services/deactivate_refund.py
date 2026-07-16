from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from django.utils import timezone

from apps.vpn.models import VPNAccess
from apps.vpn.selectors import deactivate_vpn_refund_conditionally

if TYPE_CHECKING:
    from apps.users.models import SystemUser


def _schedule_reconcile() -> None:
    from apps.vpn.tasks import reconcile_vpn_nodes_task

    reconcile_vpn_nodes_task.delay()


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class DeactivateVPNRefundService:
    schedule_reconcile: Callable[[], None]
    deactivate_conditionally: Callable[..., bool] = deactivate_vpn_refund_conditionally

    def __call__(
        self, *, access: VPNAccess, actor: SystemUser, reason: str
    ) -> bool:
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ValueError("refund reason is required")
        changed = self.deactivate_conditionally(
            access=access,
            actor_id=actor.pk,
            reason=normalized_reason,
            now=timezone.now(),
        )
        if changed:
            try:
                self.schedule_reconcile()
            except Exception:
                pass
        return changed


def get_deactivate_vpn_refund_service() -> DeactivateVPNRefundService:
    return DeactivateVPNRefundService(schedule_reconcile=_schedule_reconcile)
