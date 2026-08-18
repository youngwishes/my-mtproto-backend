from __future__ import annotations

from typing import TYPE_CHECKING

from apps.payments.apple_cashback import (
    APPLES_PER_DAY,
    AppleLevelDTO,
    build_apple_purchase_identity_key,
    calculate_apples,
    get_apple_level,
)
from apps.payments.enums import AppleRedemptionModeEnum

if TYPE_CHECKING:
    from apps.payments.models import AppleCashbackPurchase, AppleRedemption

__all__ = [
    "APPLES_PER_DAY",
    "AppleLevelDTO",
    "AppleRedemptionModeEnum",
    "AppleCashbackPurchase",
    "AppleRedemption",
    "build_apple_purchase_identity_key",
    "calculate_apples",
    "get_apple_level",
]


def __getattr__(name: str) -> object:
    if name in __all__:
        from apps.payments.models import AppleCashbackPurchase, AppleRedemption

        return {
            "AppleCashbackPurchase": AppleCashbackPurchase,
            "AppleRedemption": AppleRedemption,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
