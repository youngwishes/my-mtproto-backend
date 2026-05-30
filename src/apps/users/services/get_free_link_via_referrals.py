from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.service import BaseServiceError, log_service_error
from apps.users.models import SystemUser
from apps.vds.services import get_issue_key_service


class AlreadyUsedProgram(BaseServiceError):
    """🔒 Вы уже воспользовались реферальной программой."""


class NotEnoughReferrals(BaseServiceError):
    """🔒 Пригласите как минимум 5 пользователей. Используйте для этого вашу реферальную ссылку. Каждый приглашенный пользователь должен воспользоваться бесплатным периодом в 14 дней по вашей реферальной ссылке."""


@dataclass(kw_only=True, frozen=True, slots=True)
class Response:
    expired_date: str
    link: str

    def asdict(self) -> dict:
        return asdict(self)


@dataclass(kw_only=True, slots=True, frozen=True)
class GetReferralVDSLinkService:
    @log_service_error
    def __call__(self, *, username: str) -> Response:
        user = SystemUser.objects.get(username=username)

        if user.referral_link_activated_count >= settings.REFERRAL_LINKS_LIMIT:
            raise AlreadyUsedProgram(telegram_id=username)

        if (
            SystemUser.objects.filter(
                invited_from_username=username, referral_activated=True
            ).count()
            < settings.INVITE_MUST_COUNT
        ):
            raise NotEnoughReferrals(telegram_id=username)

        expired_date = timezone.now() + timedelta(days=14)

        with transaction.atomic():
            mtproto_key = get_issue_key_service()(user=user, expired_date=expired_date)
            user.referral_link_activated_count += 1
            user.save(update_fields=["referral_link_activated_count"])

        return Response(
            link=mtproto_key.get_proxy_link(),
            expired_date=expired_date.date().strftime("%d.%m.%y"),
        )


def get_referral_vds_link_service() -> GetReferralVDSLinkService:
    return GetReferralVDSLinkService()
