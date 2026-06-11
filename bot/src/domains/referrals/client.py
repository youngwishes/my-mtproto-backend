from __future__ import annotations

from dataclasses import dataclass, field
from typing import final

from core.backend_client import BackendClient
from core.handle_error import log_service_error


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReferralCabinet:
    total_referrals_count: int | None
    active_referrals_count: int | None
    referral_link: str | None
    link_activated_count: int | None


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReferralLink:
    link: str
    expired_date: str


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReferralsClient:
    _http: BackendClient = field(default_factory=BackendClient)

    @log_service_error
    async def get_cabinet(self, *, telegram_id: str) -> ReferralCabinet:
        result = await self._http.post(
            path="/api/v1/users/referral/cabinet/",
            telegram_id=telegram_id,
            data={"username": telegram_id},
        )
        return ReferralCabinet(
            total_referrals_count=result["total_referrals_count"],
            active_referrals_count=result["active_referrals_count"],
            referral_link=result["referral_link"],
            link_activated_count=result["link_activated_count"],
        )

    @log_service_error
    async def get_referral_link(self, *, telegram_id: str) -> ReferralLink:
        result = await self._http.post(
            path="/api/v1/users/referral/link/",
            telegram_id=telegram_id,
            data={"username": telegram_id},
        )
        return ReferralLink(link=result["link"], expired_date=result["expired_date"])


def get_referrals_client() -> ReferralsClient:
    return ReferralsClient()
