from dataclasses import dataclass

from django.conf import settings

from apps.core.service import log_service_error
from apps.users.models import SystemUser


@dataclass(kw_only=True, slots=True, frozen=True)
class CheckFirstMonthFreeService:
    @log_service_error
    def __call__(self, *, username: str, telegram_username: str | None = None) -> bool:
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

        first_month_free_used = not user.first_month_free_used
        free_count = SystemUser.objects.filter(first_month_free_used=True).count()
        if free_count >= settings.FIRST_MONTH_LIMIT:
            first_month_free_used = False
        return first_month_free_used


def get_check_first_month_free_service() -> CheckFirstMonthFreeService:
    return CheckFirstMonthFreeService()
