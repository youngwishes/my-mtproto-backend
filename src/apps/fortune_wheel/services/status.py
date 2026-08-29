from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import final

from django.db import DatabaseError
from django.utils import timezone

from apps.fortune_wheel.constants import SPIN_COOLDOWN
from apps.fortune_wheel.exceptions import FortuneWheelRetryable
from apps.fortune_wheel.selectors import get_fortune_user, get_latest_fortune_spin
from apps.fortune_wheel.services.dtos import FortuneWheelStatusOut


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class GetFortuneWheelStatusService:
    clock: Callable[[], datetime]

    def __call__(self, *, telegram_id: str) -> FortuneWheelStatusOut:
        try:
            return self._get_status(telegram_id=telegram_id)
        except DatabaseError as exc:
            raise FortuneWheelRetryable(telegram_id) from exc

    def _get_status(self, *, telegram_id: str) -> FortuneWheelStatusOut:
        user = get_fortune_user(telegram_id=telegram_id)
        if user is None or not user.legal_terms_accepted:
            return FortuneWheelStatusOut(
                registered=False,
                can_spin=False,
                last_prize=None,
                next_spin_at=None,
            )

        latest_spin = get_latest_fortune_spin(user_id=user.pk)
        if latest_spin is None or latest_spin.created_at is None:
            return FortuneWheelStatusOut(
                registered=True,
                can_spin=True,
                last_prize=None,
                next_spin_at=None,
            )

        next_spin_at = latest_spin.created_at + SPIN_COOLDOWN
        return FortuneWheelStatusOut(
            registered=True,
            can_spin=self.clock() >= next_spin_at,
            last_prize=latest_spin.prize_apples,
            next_spin_at=next_spin_at,
        )


def get_fortune_wheel_status_service() -> GetFortuneWheelStatusService:
    return GetFortuneWheelStatusService(clock=timezone.now)
