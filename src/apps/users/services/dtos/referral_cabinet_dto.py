from __future__ import annotations

from dataclasses import dataclass

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class ReferralCabinetOut(BaseServiceDTO):
    """Данные реферального кабинета пользователя."""

    total_referrals_count: int | None
    active_referrals_count: int | None
    referral_link: str | None
    link_activated_count: int | None
