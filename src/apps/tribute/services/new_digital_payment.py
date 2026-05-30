from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.core.bot import TelegramBot
from apps.core.service import log_service_error
from apps.tribute.models import TributeDigitalPayment
from apps.tribute.services.dtos import NewDigitalPaymentDTO
from apps.users.models import SystemUser
from apps.vds.services import get_issue_key_service


@dataclass(kw_only=True, slots=True, frozen=True)
class TributeDigitalPaymentService:
    @log_service_error
    def __call__(self, *, new_digital_payment: NewDigitalPaymentDTO) -> None:
        user, _ = SystemUser.objects.get_or_create(
            username=new_digital_payment.telegram_user_id
        )
        with transaction.atomic():
            payment = TributeDigitalPayment.objects.create(**asdict(new_digital_payment))
            mtproto_key = get_issue_key_service()(
                user=user,
                expired_date=timezone.now() + timedelta(days=30),
                payment=payment,
            )
            payment.is_success = True
            payment.save(update_fields=["is_success"])

        TelegramBot.send_proxy_link(
            chat_id=user.username,
            link=mtproto_key.get_proxy_link(),
        )


def get_tribute_digital_payment_service() -> TributeDigitalPaymentService:
    return TributeDigitalPaymentService()
