from __future__ import annotations

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.notifications.services import SendNotificationService
from apps.payments.enums import PaymentKindEnum
from apps.payments.selectors import (
    get_crypto_intent_for_notification,
    mark_crypto_notification_sent,
)
from apps.vds.selectors import get_active_key


@shared_task(bind=True, max_retries=3)
def notify_crypto_purchase_task(self, intent_id: int) -> None:
    """Надёжно доставляет сохранённый результат Crypto Pay инициатору."""
    intent = get_crypto_intent_for_notification(intent_id=intent_id)
    if intent is None:
        return

    try:
        if intent.purchase_kind == PaymentKindEnum.SUBSCRIPTION:
            key = get_active_key(user=intent.initiator)
            slug = "proxy_purchased"
            context = {
                "expired_date": key.expired_date.date().strftime("%d.%m.%y")
            }
        elif intent.purchase_kind == PaymentKindEnum.VPN_SUBSCRIPTION:
            subscription = intent.payment.user.vpn_subscription
            slug = "crypto_vpn_purchased"
            context = {
                "expired_at": subscription.expired_at.strftime(
                    "%d.%m.%Y %H:%M UTC"
                ),
                "subscription_url": (
                    f"{settings.VPN_SUBSCRIPTION_BASE_URL.rstrip('/')}"
                    "/api/v1/vpn/subscriptions/"
                    f"{subscription.token}/"
                ),
            }
        else:
            slug = "crypto_gift_certificate_purchased"
            context = {"code": intent.payment.gift_certificate.code}

        SendNotificationService(slug=slug, context=context)(
            chat_id=int(intent.initiator.username),
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)

    mark_crypto_notification_sent(
        intent_id=intent.pk,
        sent_at=timezone.now(),
    )
