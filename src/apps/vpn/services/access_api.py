from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol, final

from django.conf import settings
from django.utils import timezone

from apps.users.selectors import get_user_by_username
from apps.vpn.enums import VPNAccessState
from apps.vpn.exceptions import VPNAccessExpired, VPNAccessNotFound
from apps.vpn.selectors import get_vpn_access_by_user_id
from apps.vpn.services.reissue import VPNReissueResult, get_reissue_vpn_access_service

if TYPE_CHECKING:
    from apps.users.models import SystemUser
    from apps.vpn.models import VPNAccess


class ReissueAccess(Protocol):
    def __call__(self, *, access: VPNAccess) -> VPNReissueResult: ...


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class VPNAccessStatusOut:
    status: str
    expired_at: datetime | None = None
    subscription_url: str | None = None


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class GetVPNAccessStatusService:
    get_user: Callable[..., SystemUser | None]
    get_access: Callable[..., VPNAccess | None]
    now: Callable[[], datetime]
    subscription_base_url: str

    def __call__(self, *, username: str) -> VPNAccessStatusOut:
        user = self.get_user(username=username)
        if user is None:
            return VPNAccessStatusOut(status="NOT_PURCHASED")
        access = self.get_access(user_id=user.pk)
        if access is None:
            return VPNAccessStatusOut(status="NOT_PURCHASED")
        if access.state == VPNAccessState.DISABLED_REFUND:
            return VPNAccessStatusOut(status="DISABLED", expired_at=access.expired_at)
        if access.state == VPNAccessState.EXPIRED or access.expired_at <= self.now():
            return VPNAccessStatusOut(status="EXPIRED", expired_at=access.expired_at)
        if (
            access.state == VPNAccessState.READY
            and access.published_uuid is not None
            and access.published_revision == access.desired_revision
        ):
            url = (
                f"{self.subscription_base_url.rstrip('/')}/{access.subscription_token}/"
            )
            return VPNAccessStatusOut(
                status="READY",
                expired_at=access.expired_at,
                subscription_url=url,
            )
        return VPNAccessStatusOut(status="PREPARING", expired_at=access.expired_at)


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReissueVPNAccessByUsernameService:
    get_user: Callable[..., SystemUser | None]
    get_access: Callable[..., VPNAccess | None]
    reissue: ReissueAccess

    def __call__(self, *, username: str) -> VPNReissueResult:
        user = self.get_user(username=username)
        access = None if user is None else self.get_access(user_id=user.pk)
        if access is None or access.state == VPNAccessState.DISABLED_REFUND:
            raise VPNAccessNotFound(username)
        if access.state == VPNAccessState.EXPIRED:
            raise VPNAccessExpired(username)
        return self.reissue(access=access)


def get_vpn_access_status_service() -> GetVPNAccessStatusService:
    return GetVPNAccessStatusService(
        get_user=get_user_by_username,
        get_access=get_vpn_access_by_user_id,
        now=timezone.now,
        subscription_base_url=settings.VPN_SUBSCRIPTION_BASE_URL,
    )


def get_reissue_vpn_access_by_username_service() -> ReissueVPNAccessByUsernameService:
    return ReissueVPNAccessByUsernameService(
        get_user=get_user_by_username,
        get_access=get_vpn_access_by_user_id,
        reissue=get_reissue_vpn_access_service(),
    )
