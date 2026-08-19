from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


APPLES_PER_DAY = 15


@dataclass(frozen=True, kw_only=True, slots=True)
class AppleLevelDTO:
    name: str
    rate_percent: int
    next_level_purchase_count: int | None


def get_apple_level(*, eligible_purchase_count: int) -> AppleLevelDTO:
    """Return the fixed loyalty level for completed eligible purchases."""
    if eligible_purchase_count < 4:
        return AppleLevelDTO(
            name="Новичок",
            rate_percent=5,
            next_level_purchase_count=4,
        )
    if eligible_purchase_count < 7:
        return AppleLevelDTO(
            name="Садовник",
            rate_percent=10,
            next_level_purchase_count=7,
        )
    return AppleLevelDTO(
        name="Мастер сада",
        rate_percent=15,
        next_level_purchase_count=None,
    )


def calculate_apples(*, nominal_rub_amount: Decimal, rate_percent: int) -> int:
    """Calculate whole apples from nominal RUB using mathematical half-up rounding."""
    cashback = nominal_rub_amount * Decimal(rate_percent) / Decimal(100)
    return int(cashback.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def build_apple_purchase_identity_key(
    *, provider: str, charge_id: str, kind: str
) -> str:
    """Encode the provider payment identity used for exactly-once cashback."""
    return f"{provider}:{charge_id}:{kind}"
