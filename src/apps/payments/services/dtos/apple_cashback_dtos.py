from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class HistoricalPurchaseReplayDTO(BaseServiceDTO):
    """Successful replay of a pre-launch payment with no product mutation."""

    kind: Literal["historical_replay"] = "historical_replay"


@dataclass(kw_only=True, frozen=True, slots=True)
class ApplePurchaseOutcomeDTO(BaseServiceDTO):
    """Saved loyalty outcome returned for a successful eligible purchase."""

    apples_earned: int
    rate_percent: int
    balance: int
    eligible_purchase_count: int
    level: str
    level_up: bool
    next_purchase_rate_percent: int
