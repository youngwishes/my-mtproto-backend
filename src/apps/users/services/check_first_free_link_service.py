from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, final

from django.conf import settings

from apps.core.decorators import log_service_error
from apps.users.enums import FreeAvailable
from apps.users.exceptions import LegalTermsNotAccepted
from apps.users.services.dtos import CheckFirstFreeLinkIn

if TYPE_CHECKING:
    from apps.users.models import SystemUser


class _GetUserByUsername(Protocol):
    def __call__(self, *, username: str) -> SystemUser | None: ...


class _GetFreeUsedCount(Protocol):
    def __call__(self) -> int: ...


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class CheckFirstFreeLinkService:
    """Read-only проверяет бесплатный период согласившегося пользователя."""

    get_user: _GetUserByUsername
    get_free_used_count: _GetFreeUsedCount

    @log_service_error
    def __call__(self, *, data: CheckFirstFreeLinkIn) -> FreeAvailable:
        user = self.get_user(username=data.username)
        if user is None or not user.legal_terms_accepted:
            raise LegalTermsNotAccepted(telegram_id=data.username)

        if user.first_month_free_used:
            return FreeAvailable.NOT_AVAILABLE

        if self.get_free_used_count() >= settings.FIRST_MONTH_LIMIT:
            if user.invited_from_username:
                return FreeAvailable.TWO_WEEK
            return FreeAvailable.WEEK

        return FreeAvailable.MONTH


def get_check_first_free_link_service() -> CheckFirstFreeLinkService:
    from apps.users.selectors import get_free_used_count, get_user_by_username

    return CheckFirstFreeLinkService(
        get_user=get_user_by_username,
        get_free_used_count=get_free_used_count,
    )
