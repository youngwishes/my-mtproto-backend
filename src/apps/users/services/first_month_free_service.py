from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from apps.core.service import BaseServiceError, log_service_error
from apps.users.models import SystemUser
from apps.vds.models import MTPRotoKey, VDSInstance
from apps.vds.services import get_add_new_key_service_factory


class AlreadyUsedFree(BaseServiceError):
    """🔒 Вы уже получили беплатную ссылку."""


@dataclass(kw_only=True, slots=True, frozen=True)
class FirstLinkFreeService:
    @log_service_error
    def __call__(self, *, username: str) -> dict:
        try:
            user = SystemUser.objects.get(username=username)
        except SystemUser.DoesNotExist:
            user = SystemUser.objects.create(
                username=username,
            )
        if user.first_month_free_used:
            raise AlreadyUsedFree(
                telegram_id=username,
            )

        expired_date = timezone.now() + timedelta(days=30)
        free_count = SystemUser.objects.filter(first_month_free_used=True).count()
        if free_count >= settings.FIRST_MONTH_LIMIT:
            expired_date = timezone.now() + timedelta(days=7)

        server = VDSInstance.objects.get_least_populated()
        with transaction.atomic():
            response = get_add_new_key_service_factory()(
               server=server,
               username=str(user.username),
            )
            mtproto_key = MTPRotoKey.objects.create(
                vds=server,
                user=user,
                payment=None,
                token=response.key,
                tls_domain=response.tls_domain,
                node_number=response.node_number,
                expired_date=expired_date,
            )
            user.first_month_free_used = True
            user.save(update_fields=["first_month_free_used"])

        return {
            "link": mtproto_key.get_proxy_link(),
        }


def get_first_link_free_service() -> FirstLinkFreeService:
    return FirstLinkFreeService()
