from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from src.core.backend_client import BackendClient

_CABINET_PATH = "/api/v1/users/referral/cabinet/"


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReferralCabinet:
    total_referrals_count: int | None
    active_referrals_count: int | None
    referral_link: str | None
    apple_balance: int | None


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReferralsClient:
    backend: BackendClient

    async def get_cabinet(self, *, telegram_id: str) -> ReferralCabinet:
        response = await self.backend.post(
            _CABINET_PATH, data={"username": telegram_id}, telegram_id=telegram_id
        )
        return ReferralCabinet(**response)
