from dataclasses import dataclass
from enum import StrEnum

from django.conf import settings

from apps.core.service import log_service_error
from apps.users.models import SystemUser


class FreeAvailable(StrEnum):
    MONTH = "MONTH"
    TWO_WEEK = "TWO_WEEK"
    WEEK = "WEEK"
    NOT_AVAILABLE = "NOT_AVAILABLE"


@dataclass(kw_only=True, slots=True, frozen=True)
class CheckFreeLinkService:
    @log_service_error
    def __call__(self, *, username: str, telegram_username: str | None = None) -> FreeAvailable:
        try:
            user = SystemUser.objects.get(username=username)
            if not user.telegram_username:
                user.telegram_username = telegram_username
                user.save(update_fields=["telegram_username"])
        except SystemUser.DoesNotExist:
            user = SystemUser.objects.create(
                username=username,
                telegram_username=telegram_username,
            )

        available_free_period = FreeAvailable.MONTH
        free_count = SystemUser.objects.filter(first_month_free_used=True).count()

        if free_count >= settings.FIRST_MONTH_LIMIT:
            available_free_period = FreeAvailable.WEEK

        if user.first_month_free_used:
            available_free_period = FreeAvailable.NOT_AVAILABLE

        return available_free_period


def get_check_free_link_service() -> CheckFreeLinkService:
    return CheckFreeLinkService()
