from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import final
from uuid import UUID, uuid4

from django.utils import timezone

from apps.vpn.enums import VPNAccessState
from apps.vpn.exceptions import (
    VPNAccessExpired,
    VPNReissueConflict,
    VPNReissueInProgress,
    VPNReissueNotEligible,
)
from apps.vpn.models import VPNAccess
from apps.vpn.selectors import stage_vpn_access_reissue


def _schedule_reconcile() -> None:
    from apps.vpn.tasks import reconcile_vpn_nodes_task

    reconcile_vpn_nodes_task.delay()


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class VPNReissueResult:
    access_id: int
    desired_uuid: UUID
    desired_revision: int


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReissueVPNAccessService:
    schedule_reconcile: Callable[[], None]
    generate_uuid: Callable[[], UUID] = uuid4
    stage_reissue: Callable[..., bool] = stage_vpn_access_reissue

    def __call__(self, *, access: VPNAccess) -> VPNReissueResult:
        telegram_id = access.user.username
        if access.expired_at <= timezone.now():
            raise VPNAccessExpired(telegram_id)
        if access.state == VPNAccessState.PREPARING:
            raise VPNReissueInProgress(telegram_id)
        if access.state != VPNAccessState.READY or access.published_uuid is None:
            raise VPNReissueNotEligible(telegram_id)
        new_uuid = self.generate_uuid()
        changed = self.stage_reissue(access=access, new_uuid=new_uuid, now=timezone.now())
        if changed:
            try:
                self.schedule_reconcile()
            except Exception:
                pass
        if not changed:
            raise VPNReissueConflict(telegram_id)
        return VPNReissueResult(
            access_id=access.pk,
            desired_uuid=new_uuid,
            desired_revision=access.desired_revision + 1,
        )


def get_reissue_vpn_access_service() -> ReissueVPNAccessService:
    return ReissueVPNAccessService(schedule_reconcile=_schedule_reconcile)
