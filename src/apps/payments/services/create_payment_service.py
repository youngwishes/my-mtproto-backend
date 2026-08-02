from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Protocol, final

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.decorators import log_service_error
from apps.payments.exceptions import BadPaymentData
from apps.notifications.services.send_notification_service import SendNotificationService
from apps.payments.selectors import create_subscription_payment
from apps.payments.services.extend_key_service import ExtendKeyService, get_extend_key_service
from apps.users.selectors import get_user_by_username
from apps.vds.selectors import get_active_key
from apps.vds.services import get_issue_key_on_commit_service

if TYPE_CHECKING:
    from apps.payments.services.dtos import CreatePaymentIn
    from apps.vds.services import IssueKeyService


class NotifyPaymentSuccess(Protocol):
    def __call__(self, *, chat_id: int, expired_date: str) -> None: ...


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
    issue_key_service: IssueKeyService
    notify_success: NotifyPaymentSuccess

    @log_service_error
    def __call__(
        self,
        *,
        payment: CreatePaymentIn,
        send_success_notification: bool = True,
    ) -> None:
        user = get_user_by_username(username=payment.username)
        if user is None:
            raise BadPaymentData(telegram_id=payment.username)

        with transaction.atomic():
            active_key = get_active_key(user=user)
            if active_key:
                self.extend_key_service(key=active_key)
                key = active_key
            else:
                key = self.issue_key_service(
                    user=user,
                    expired_date=timezone.now() + timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS),
                )

            create_subscription_payment(
                user_id=user.pk,
                key_id=key.pk,
                charge_id=payment.charge_id,
                provider=payment.provider,
            )

        if send_success_notification:
            # Уведомление — best-effort: платёж уже проведён и закоммичен, сбой
            # доставки в Telegram не должен превращать успешный платёж в 500.
            try:
                self.notify_success(
                    chat_id=int(user.username),
                    expired_date=key.expired_date.date().strftime("%d.%m.%y"),
                )
            except Exception:
                pass


def _notify_payment_success(*, chat_id: int, expired_date: str) -> None:
    SendNotificationService(
        slug="proxy_purchased",
        context={"expired_date": expired_date},
    )(chat_id=chat_id)


def get_create_payment_service() -> CreatePaymentService:
    return CreatePaymentService(
        extend_key_service=get_extend_key_service(),
        issue_key_service=get_issue_key_on_commit_service(),
        notify_success=_notify_payment_success,
    )
