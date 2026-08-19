from __future__ import annotations

from dataclasses import dataclass

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class AppleStatusIn(BaseServiceDTO):
    username: str


@dataclass(kw_only=True, frozen=True, slots=True)
class AppleStatusOut(BaseServiceDTO):
    balance: int
    eligible_purchase_count: int
    level: str
    rate_percent: int
    next_level_purchase_count: int | None
    purchases_to_next_level: int | None
    is_max_level: bool
    redeemable_days: int
    missing_apples: int
    has_existing_key: bool


@dataclass(kw_only=True, frozen=True, slots=True)
class AppleRedemptionPreviewIn(BaseServiceDTO):
    username: str
    mode: str


@dataclass(kw_only=True, frozen=True, slots=True)
class AppleRedemptionPreviewOut(BaseServiceDTO):
    confirmation_id: int
    mode: str
    apples_spent: int
    days: int
    projected_expired_date: str


@dataclass(kw_only=True, frozen=True, slots=True)
class AppleRedemptionConfirmIn(BaseServiceDTO):
    username: str
    confirmation_id: int


@dataclass(kw_only=True, frozen=True, slots=True)
class AppleRedemptionConfirmOut(BaseServiceDTO):
    apples_spent: int
    days: int
    expired_date: str
    balance: int
