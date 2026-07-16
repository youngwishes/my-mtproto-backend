from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import final

from django.utils import timezone

from apps.vpn.selectors import expire_vpn_access_conditionally, get_due_vpn_accesses


def _schedule_reconcile() -> None:
    from apps.vpn.tasks import reconcile_vpn_nodes_task

    reconcile_vpn_nodes_task.delay()


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ExpireVPNAccessesService:
    schedule_reconcile: Callable[[], None]
    get_due_accesses: Callable[..., object] = get_due_vpn_accesses
    expire_conditionally: Callable[..., bool] = expire_vpn_access_conditionally

    def __call__(self) -> int:
        now = timezone.now()
        changed = sum(
            self.expire_conditionally(access=access, now=now)
            for access in self.get_due_accesses(now=now)
        )
        if changed:
            try:
                self.schedule_reconcile()
            except Exception:
                pass
        return changed


def get_expire_vpn_accesses_service() -> ExpireVPNAccessesService:
    return ExpireVPNAccessesService(schedule_reconcile=_schedule_reconcile)
