from __future__ import annotations

from datetime import timedelta


SPIN_COOLDOWN = timedelta(days=10)
PRIZE_WEIGHTS = (
    (5, 20),
    (10, 30),
    (15, 25),
    (25, 20),
    (60, 4),
    (100, 1),
)


def prize_for_ticket(*, ticket: int) -> int:
    upper_bound = 0
    for prize, weight in PRIZE_WEIGHTS:
        upper_bound += weight
        if ticket < upper_bound:
            return prize
    raise AssertionError("ticket must be in range 0..99")
