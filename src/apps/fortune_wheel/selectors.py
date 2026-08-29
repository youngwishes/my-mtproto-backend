from __future__ import annotations

from datetime import datetime

from apps.fortune_wheel.models import FortuneSpin
from apps.users.models import SystemUser


def get_fortune_user(*, telegram_id: str) -> SystemUser | None:
    return SystemUser.objects.filter(username=telegram_id).first()


def get_fortune_user_for_update(*, telegram_id: str) -> SystemUser | None:
    return SystemUser.objects.select_for_update().filter(username=telegram_id).first()


def get_latest_fortune_spin(*, user_id: int) -> FortuneSpin | None:
    return (
        FortuneSpin.objects.filter(user_id=user_id)
        .order_by("-created_at", "-pk")
        .first()
    )


def create_fortune_spin(
    *,
    user_id: int,
    prize_apples: int,
    spun_at: datetime,
) -> FortuneSpin:
    spin = FortuneSpin.objects.create(
        user_id=user_id,
        prize_apples=prize_apples,
    )
    FortuneSpin.objects.filter(pk=spin.pk).update(created_at=spun_at)
    spin.created_at = spun_at
    return spin
