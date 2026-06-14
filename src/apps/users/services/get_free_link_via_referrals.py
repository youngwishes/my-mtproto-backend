from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, final

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.decorators import log_service_error
from apps.users.exceptions import AlreadyUsedProgram, NotEnoughReferrals
from apps.users.models import SystemUser
from apps.users.selectors import get_active_referrals_count, get_user_by_username
from apps.users.services.dtos import IssuedKeyOut
from apps.vds.selectors import get_active_key

if TYPE_CHECKING:
    from apps.vds.services.issue_key_service import IssueKeyService


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class GetReferralVDSLinkService:
    """Выдаёт бесплатный ключ по реферальной программе.

    Условия: пользователь не использовал программу ранее,
    и у него >= INVITE_MUST_COUNT активных рефералов.
    """

    issue_key_service: IssueKeyService

    @log_service_error
    def __call__(self, *, username: str) -> IssuedKeyOut:
        user = get_user_by_username(username=username)

        if user.referral_link_activated_count >= settings.REFERRAL_LINKS_LIMIT:
            raise AlreadyUsedProgram(telegram_id=username)

        if get_active_referrals_count(username=username) < settings.INVITE_MUST_COUNT:
            raise NotEnoughReferrals(telegram_id=username)

        with transaction.atomic():
            active_key = get_active_key(user=user)
            if active_key is not None:
                # Награда — бонус +14 дней к текущей подписке (продлеваем существующий
                # ключ, не пересоздаём): иначе активный ключ был бы затёрт 14 днями.
                active_key.expired_date += timedelta(days=14)
                active_key.save(update_fields=["expired_date"])
                expired_date = active_key.expired_date
            else:
                key = self.issue_key_service(
                    user=user, expired_date=timezone.now() + timedelta(days=14)
                )
                expired_date = key.expired_date
            user.referral_link_activated_count += 1
            user.save(update_fields=["referral_link_activated_count"])

        return IssuedKeyOut(
            expired_date=expired_date.date().strftime("%d.%m.%y"),
        )


def get_referral_vds_link_service() -> GetReferralVDSLinkService:
    from apps.vds.services import get_issue_key_service

    return GetReferralVDSLinkService(
        issue_key_service=get_issue_key_service(),
    )
