from dataclasses import dataclass

from django.conf import settings

from apps.core.service import log_service_error
from apps.users.models import SystemUser


@dataclass(kw_only=True, slots=True, frozen=True)
class CheckFirstMonthFreeService:
    @log_service_error
    def __call__(self, *, username: str) -> bool:
        try:
            user = SystemUser.objects.get(username=username)
        except SystemUser.DoesNotExist:
            user = SystemUser.objects.create(username=username)

        first_month_free_used = not user.first_month_free_used
        free_count = SystemUser.objects.filter(first_month_free_used=True).count()
        if free_count >= settings.FIRST_MONTH_LIMIT:
            first_month_free_used = False
        return first_month_free_used


def get_check_first_month_free_service() -> CheckFirstMonthFreeService:
    return CheckFirstMonthFreeService()
