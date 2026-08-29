from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import final

from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.fortune_wheel.constants import SPIN_COOLDOWN, prize_for_ticket
from apps.fortune_wheel.exceptions import (
    FortuneWheelCooldown,
    FortuneWheelRegistrationRequired,
    FortuneWheelRetryable,
)
from apps.fortune_wheel.selectors import (
    create_fortune_spin,
    get_fortune_user_for_update,
    get_latest_fortune_spin,
)
from apps.fortune_wheel.services.dtos import FortuneWheelSpinOut


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class SpinFortuneWheelService:
    clock: Callable[[], datetime]
    ticket_source: Callable[[], int]

    def __call__(self, *, telegram_id: str) -> FortuneWheelSpinOut:
        try:
            with transaction.atomic():
                return self._spin(telegram_id=telegram_id)
        except DatabaseError as exc:
            raise FortuneWheelRetryable(telegram_id) from exc

    def _spin(self, *, telegram_id: str) -> FortuneWheelSpinOut:
        user = get_fortune_user_for_update(telegram_id=telegram_id)
        if user is None or not user.legal_terms_accepted:
            raise FortuneWheelRegistrationRequired(telegram_id)

        spun_at = self.clock()
        latest_spin = get_latest_fortune_spin(user_id=user.pk)
        if latest_spin is not None and latest_spin.created_at is not None:
            next_spin_at = latest_spin.created_at + SPIN_COOLDOWN
            if spun_at < next_spin_at:
                raise FortuneWheelCooldown(
                    telegram_id,
                    last_prize=latest_spin.prize_apples,
                    next_spin_at=next_spin_at,
                )

        prize_apples = prize_for_ticket(ticket=self.ticket_source())
        user.apple_balance += prize_apples
        user.save(update_fields=["apple_balance"])
        spin = create_fortune_spin(
            user_id=user.pk,
            prize_apples=prize_apples,
            spun_at=spun_at,
        )
        assert spin.created_at is not None
        return FortuneWheelSpinOut(
            prize_apples=prize_apples,
            spun_at=spin.created_at,
            next_spin_at=spin.created_at + SPIN_COOLDOWN,
        )


def get_spin_fortune_wheel_service() -> SpinFortuneWheelService:
    return SpinFortuneWheelService(
        clock=timezone.now,
        ticket_source=lambda: secrets.randbelow(100),
    )
