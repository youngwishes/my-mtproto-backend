from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.payments.models import AppleCashbackPurchase, AppleRedemption

__all__ = [
    "AppleCashbackPurchase",
    "AppleRedemption",
]


def __getattr__(name: str) -> object:
    if name in __all__:
        from apps.payments.models import AppleCashbackPurchase, AppleRedemption

        return {
            "AppleCashbackPurchase": AppleCashbackPurchase,
            "AppleRedemption": AppleRedemption,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
