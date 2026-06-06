from __future__ import annotations

from dataclasses import dataclass
from typing import final

from django.conf import settings

from apps.core.decorators import log_service_error
from apps.users.enums import FreeAvailable
from apps.users.models import SystemUser
from apps.users.selectors import get_free_used_count, get_user_by_username
from apps.users.services.dtos import CheckFirstFreeLinkIn


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class CheckFirstFreeLinkService:
    """Проверяет доступность бесплатного периода для пользователя.

    Побочный эффект: создаёт пользователя, если его нет,
    и обновляет telegram_username.
    """

    @log_service_error
    def __call__(self, *, data: CheckFirstFreeLinkIn) -> FreeAvailable:
        user = self._ensure_user(data=data)

        if user.first_month_free_used:
            return FreeAvailable.NOT_AVAILABLE

        if get_free_used_count() >= settings.FIRST_MONTH_LIMIT:
            if user.invited_from_username:
                return FreeAvailable.TWO_WEEK
            return FreeAvailable.WEEK

        return FreeAvailable.MONTH

    def _ensure_user(self, *, data: CheckFirstFreeLinkIn) -> SystemUser:
        user = get_user_by_username(username=data.username)

        if user is None:
            return SystemUser.objects.create(
                username=data.username,
                telegram_username=data.telegram_username,
                invited_from_username=data.invited_from_username,
            )

        if not user.telegram_username:
            user.telegram_username = data.telegram_username
            user.save(update_fields=["telegram_username"])

        return user


def get_check_first_free_link_service() -> CheckFirstFreeLinkService:
    return CheckFirstFreeLinkService()
