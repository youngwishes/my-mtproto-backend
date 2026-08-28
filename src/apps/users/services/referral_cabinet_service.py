from __future__ import annotations

from dataclasses import dataclass
from typing import final

from apps.users.selectors import (
    get_active_referrals_count,
    get_total_referrals_count,
    get_user_by_username,
)
from apps.users.services.dtos import ReferralCabinetOut


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReferralCabinetService:
    """Возвращает данные реферального кабинета пользователя."""

    def __call__(self, *, username: str) -> ReferralCabinetOut:
        user = get_user_by_username(username=username)

        if user is None:
            return ReferralCabinetOut(
                total_referrals_count=None,
                active_referrals_count=None,
                referral_link=None,
                apple_balance=None,
            )

        return ReferralCabinetOut(
            total_referrals_count=get_total_referrals_count(username=username),
            active_referrals_count=get_active_referrals_count(username=username),
            referral_link=user.referral_link,
            apple_balance=user.apple_balance,
        )


def get_referral_cabinet_service() -> ReferralCabinetService:
    return ReferralCabinetService()
