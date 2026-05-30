from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.service import BaseServiceError, log_service_error
from apps.users.models import SystemUser
from apps.vds.models import MTPRotoKey
from apps.vds.services import get_issue_key_service


@dataclass(kw_only=True, frozen=True, slots=True)
class Response:
    expired_date: str
    link: str

    def asdict(self) -> dict:
        return asdict(self)


class AlreadyUsedFree(BaseServiceError):
    """🔒 Вы уже получили беплатную ссылку. Если она не работает — напишите нам в личные сообщения канала @mtproto_keys."""


@dataclass(kw_only=True, slots=True, frozen=True)
class FirstFreeLinkService:
    @log_service_error
    def __call__(self, *, username: str) -> Response:
        user, _ = SystemUser.objects.get_or_create(username=username)

        if user.first_month_free_used:
            raise AlreadyUsedFree(telegram_id=username)

        expired_date = timezone.now() + timedelta(days=30)

        free_count = SystemUser.objects.filter(first_month_free_used=True).count()
        if free_count >= settings.FIRST_MONTH_LIMIT:
            expired_date = timezone.now() + timedelta(days=7)

        if user.invited_from_username:
            expired_date = timezone.now() + timedelta(days=14)

        with transaction.atomic():
            mtproto_key = get_issue_key_service()(user=user, expired_date=expired_date)
            user.first_month_free_used = True
            if user.invited_from_username:
                user.referral_activated = True
            user.save(update_fields=["first_month_free_used", "referral_activated"])

        return Response(
            link=mtproto_key.get_proxy_link(),
            expired_date=expired_date.date().strftime("%d.%m.%y"),
        )


def get_first_free_link_service() -> FirstFreeLinkService:
    return FirstFreeLinkService()
