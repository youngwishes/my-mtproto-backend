from dataclasses import dataclass

from django.db import transaction

from apps.core.service import BaseServiceError, log_service_error
from apps.users.models import SystemUser
from apps.vds.models import MTPRotoKey, VDSInstance
from apps.vds.services import get_add_new_key_service_factory


class AlreadyUsedFree(BaseServiceError):
    """Вы уже использовали беплатную ссылку."""


@dataclass(kw_only=True, slots=True, frozen=True)
class FirstMonthFreeService:
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

        with transaction.atomic():
            server = VDSInstance.objects.get_least_populated()
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
            )
            user.first_month_free_used = True
            user.save(update_fields=["first_month_free_used"])

        return {
            "link": mtproto_key.get_proxy_link(),
        }


def get_first_month_free_service() -> FirstMonthFreeService:
    return FirstMonthFreeService()
