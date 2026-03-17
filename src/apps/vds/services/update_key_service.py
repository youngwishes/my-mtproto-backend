from dataclasses import asdict, dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.core.service import BaseServiceError, log_service_error
from apps.vds.models import MTPRotoKey, VDSInstance
from apps.vds.services import get_update_key_infra_service


class KeyDoesNotExist(BaseServiceError):
    """🔒 У вас нет активного ключа. Если вы думаете, что это ошибка, пожалуйста, свяжитесь с нами через сообщения канала — @mtproto_keys."""


class TooManyRequests(BaseServiceError):
    """🔒 Пожалуйста, подождите 5 минут с последнего обновления."""


@dataclass(kw_only=True, slots=True, frozen=True)
class Response:
    link: str
    expired_date: str

    def asdict(self) -> dict:
        return asdict(self)


@dataclass(kw_only=True, slots=True, frozen=True)
class UpdateKeyService:
    @log_service_error
    def __call__(self, *, username: str) -> Response | None:
        key = MTPRotoKey.objects.filter(
            user__username=username, is_active=True, was_deleted=False
        ).first()
        if key is None:
            raise KeyDoesNotExist(telegram_id=username)

        if key.last_update and (
            key.last_update + timedelta(minutes=5) > timezone.now()
        ):
            raise TooManyRequests(telegram_id=username)

        with transaction.atomic():
            infra = get_update_key_infra_service()
            server = VDSInstance.objects.exclude(pk=key.vds.pk).get_least_populated()
            response = infra(server=server, username=username)

            key.vds = server
            key.token = response.key
            key.tls_domain = response.tls_domain
            key.node_number = response.node_number
            key.last_update = timezone.now()
            key.save(
                update_fields=[
                    "token",
                    "tls_domain",
                    "node_number",
                    "vds",
                    "last_update",
                ]
            )

            MTPRotoKey.objects.filter(user__username=username).exclude(
                pk=key.pk
            ).delete()
        return Response(
            link=key.get_proxy_link(),
            expired_date=key.expired_date.date().strftime("%d.%m.%y"),
        )


def get_update_key_service() -> UpdateKeyService:
    return UpdateKeyService()
