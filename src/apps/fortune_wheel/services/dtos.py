from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, frozen=True, slots=True)
class FortuneWheelStatusOut(BaseServiceDTO):
    registered: bool
    can_spin: bool
    last_prize: int | None
    next_spin_at: datetime | None


@dataclass(kw_only=True, frozen=True, slots=True)
class FortuneWheelSpinOut(BaseServiceDTO):
    prize_apples: int
    spun_at: datetime
    next_spin_at: datetime
