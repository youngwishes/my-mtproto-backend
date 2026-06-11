from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, final

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.decorators import log_service_error
from apps.payments.exceptions import BadPaymentData
from apps.payments.models import Payment
from apps.notifications.services.send_notification_service import SendNotificationService
from apps.payments.services.extend_key_service import ExtendKeyService, get_extend_key_service
from apps.users.selectors import get_user_by_username
from apps.vds.selectors import get_active_key
from apps.vds.services import get_issue_key_service

if TYPE_CHECKING:
    from apps.payments.services.dtos import CreatePaymentIn


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class CreatePaymentService:
    """Оркестратор обработки платежа.

    Определяет стратегию: продлить существующий ключ или выдать новый.
    Создаёт запись Payment и делегирует нотификацию.

    Raises:
        BadPaymentData: если пользователь не найден по username.
    """

    extend_key_service: ExtendKeyService

    @log_service_error
    def __call__(self, *, payment: CreatePaymentIn) -> None:
        user = get_user_by_username(username=payment.username)
        if user is None:
            raise BadPaymentData(telegram_id=payment.username)

        active_key = get_active_key(user=user)

        with transaction.atomic():
            if active_key:
                self.extend_key_service(key=active_key)
                key = active_key
            else:
                key = get_issue_key_service()(
                    user=user,
                    expired_date=timezone.now() + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS),
                )

            Payment.objects.create(
                user=user,
                key=key,
                charge_id=payment.charge_id,
                provider=payment.provider,
            )

        SendNotificationService(
            slug="proxy_purchased",
            context={"expired_date": key.expired_date.date().strftime("%d.%m.%y")},
        )(chat_id=int(user.username))


def get_create_payment_service() -> CreatePaymentService:
    return CreatePaymentService(
        extend_key_service=get_extend_key_service(),
    )
