from dataclasses import asdict, dataclass

from django.db import transaction

from apps.core.bot import TelegramBot
from apps.core.service import log_service_error
from apps.tribute.models import TributeDigitalPayment
from apps.tribute.services.dtos import NewDigitalPaymentDTO
from apps.users.models import SystemUser
from apps.vds.models import MTPRotoKey, VDSInstance
from apps.vds.services import get_add_new_key_service_factory


@dataclass(kw_only=True, slots=True, frozen=True)
class TributeDigitalPaymentService:
    @log_service_error
    @transaction.atomic
    def __call__(self, *, new_digital_payment: NewDigitalPaymentDTO) -> None:
        payment = TributeDigitalPayment.objects.create(**asdict(new_digital_payment))
        try:
            user = SystemUser.objects.get(username=new_digital_payment.telegram_user_id)
        except SystemUser.DoesNotExist:
            user = SystemUser.objects.create(
                username=new_digital_payment.telegram_user_id
            )

        server = VDSInstance.objects.get_least_populated()
        response = get_add_new_key_service_factory()(
            server=server,
            username=str(user.username),
        )
        mtproto_key = MTPRotoKey.objects.create(
            vds=server,
            user=user,
            payment=payment,
            token=response.key,
            tls_domain=response.tls_domain,
        )
        TelegramBot().send_proxy_link(
            chat_id=user.username,
            link=mtproto_key.get_proxy_link(),
        )


def get_tribute_digital_payment_service() -> TributeDigitalPaymentService:
    return TributeDigitalPaymentService()
