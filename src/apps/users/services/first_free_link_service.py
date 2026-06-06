from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, final

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.service import log_service_error
from apps.users.exceptions import AlreadyUsedFree
from apps.users.models import SystemUser
from apps.users.selectors import get_free_used_count
from apps.users.services.dtos import IssuedKeyOut

if TYPE_CHECKING:
    from apps.vds.services.issue_key_service import IssueKeyService


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class FirstFreeLinkService:
    """Выдаёт бесплатный ключ пользователю.

    Длительность зависит от условий:
    - 30 дней — стандарт
    - 7 дней — если лимит бесплатных ключей исчерпан
    - 14 дней — если пользователь пришёл по реферальной ссылке
    """

    issue_key_service: IssueKeyService

    @log_service_error
    def __call__(self, *, username: str) -> IssuedKeyOut:
        user, _ = SystemUser.objects.get_or_create(username=username)

        if user.first_month_free_used:
            raise AlreadyUsedFree(telegram_id=username)

        expired_date = self._resolve_expired_date(user=user)

        with transaction.atomic():
            mtproto_key = self.issue_key_service(user=user, expired_date=expired_date)
            user.first_month_free_used = True
            if user.invited_from_username:
                user.referral_activated = True
            user.save(update_fields=["first_month_free_used", "referral_activated"])

        return IssuedKeyOut(
            link=mtproto_key.get_proxy_link(),
            expired_date=expired_date.date().strftime("%d.%m.%y"),
        )

    def _resolve_expired_date(self, *, user: SystemUser) -> timezone.datetime:
        expired_date = timezone.now() + timedelta(days=30)

        if get_free_used_count() >= settings.FIRST_MONTH_LIMIT:
            expired_date = timezone.now() + timedelta(days=7)

        if user.invited_from_username:
            expired_date = timezone.now() + timedelta(days=14)

        return expired_date


def get_first_free_link_service() -> FirstFreeLinkService:
    from apps.vds.services import get_issue_key_service

    return FirstFreeLinkService(
        issue_key_service=get_issue_key_service(),
    )
