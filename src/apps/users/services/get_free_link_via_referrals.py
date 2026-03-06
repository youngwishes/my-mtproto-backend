from dataclasses import asdict, dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.service import BaseServiceError, log_service_error
from apps.users.models import SystemUser
from apps.vds.models import MTPRotoKey, VDSInstance
from apps.vds.services import get_add_new_key_service_factory


class AlreadyUsedProgram(BaseServiceError):
    """🔒 Вы уже воспользовались реферальной программой."""


class NotEnoughReferrals(BaseServiceError):
    """🔒 Пригласите как минимум 5 пользователей. Используйте для этого вашу реферальную ссылку. Каждый приглашенный пользователь должен воспользоваться бесплатным периодом в 14 дней по вашей реферальной ссылке."""


@dataclass(kw_only=True, slots=True, frozen=True)
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
            SystemUser.objects.filter(invited_from_username=username, referral_activated=True).count()
            < settings.INVITE_MUST_COUNT
        ):
            raise NotEnoughReferrals(telegram_id=username)

        server = VDSInstance.objects.get_least_populated()
        with transaction.atomic():
            response = get_add_new_key_service_factory()(
                server=server,
                username=str(user.username),
            )
            expired_date = timezone.now() + timedelta(days=14)
            mtproto_key = MTPRotoKey.objects.create(
                vds=server,
                user=user,
                payment=None,
                token=response.key,
                tls_domain=response.tls_domain,
                node_number=response.node_number,
                expired_date=expired_date,
            )
            user.referral_link_activated_count += 1
            user.save(update_fields=["referral_link_activated_count"])

        return Response(
            link=mtproto_key.get_proxy_link(),
            expired_date=expired_date.date().strftime("%d.%m.%y"),
        )

def get_referral_vds_link_service() -> GetReferralVDSLinkService:
    return GetReferralVDSLinkService()
