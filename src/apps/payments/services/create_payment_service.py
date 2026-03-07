from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.core.bot import TelegramBot
from apps.payments.models import Payment
from apps.users.models import SystemUser
from apps.vds.models import MTPRotoKey, VDSInstance
from apps.vds.services import get_add_new_key_service_factory


@dataclass(kw_only=True, slots=True, frozen=True)
class CreatePaymentService:
    def __call__(self, *, username: str) -> None:
        try:
            user = SystemUser.objects.get(username=username)
        except SystemUser.DoesNotExist:
            user = SystemUser.objects.create(username=username)
        with transaction.atomic():
            server = VDSInstance.objects.get_least_populated()
            response = get_add_new_key_service_factory()(
                server=server,
                username=str(user.username),
            )
            mtproto_key = MTPRotoKey.objects.create(
                vds=server,
                user=user,
                token=response.key,
                tls_domain=response.tls_domain,
                expired_date=timezone.now() + timedelta(days=30),
                node_number=response.node_number,
            )
            TelegramBot().send_proxy_link(
                chat_id=user.username,
                link=mtproto_key.get_proxy_link(),
            )
            Payment.objects.create(
                user=user,
                key=mtproto_key,
            )


def get_create_payment_service() -> CreatePaymentService:
    return CreatePaymentService()
