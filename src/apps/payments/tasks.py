from __future__ import annotations

from html import escape
import logging
from typing import TYPE_CHECKING

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.core.telegram import (
    format_user_date,
    format_user_datetime,
    send_telegram_message,
)
from apps.notifications.selectors import get_template
from apps.payments.apple_cashback import get_apple_level
from apps.payments.enums import PaymentKindEnum
from apps.payments.exceptions import CryptoPayClientError
from apps.payments.selectors import (
    get_crypto_intent_for_notification,
    get_platega_intent_for_notification,
    mark_crypto_notification_sent,
    mark_platega_notification_sent,
)
from apps.payments.services import get_reconcile_crypto_payments_service


logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from apps.payments.models import (
        AppleCashbackPurchase,
        CryptoPaymentIntent,
        PlategaPaymentIntent,
    )


def _render_apple_cashback_block(*, purchase: AppleCashbackPurchase) -> str:
    assert purchase.rate_percent is not None
    resulting_level = get_apple_level(
        eligible_purchase_count=purchase.eligible_purchase_count_after,
    )
    previous_level = get_apple_level(
        eligible_purchase_count=purchase.eligible_purchase_count_after - 1,
    )
    lines = [
        "",
        "",
        "🍏 <b>Кэшбэк</b>",
        f"Начислено: <b>{purchase.apples_earned} 🍏</b>",
        f"Ставка: <b>{purchase.rate_percent}%</b>",
        f"Баланс: <b>{purchase.balance_after} 🍏</b>",
        f"Уровень: <b>{resulting_level.name}</b>",
    ]
    if resulting_level.name != previous_level.name:
        lines.extend(
            (
                "",
                f"🎉 Новый уровень: <b>{resulting_level.name}</b>",
                "Кэшбэк следующей покупки: "
                f"<b>{resulting_level.rate_percent}%</b>",
            )
        )
    return "\n".join(lines)


def _send_purchase_result(
    *,
    intent: CryptoPaymentIntent | PlategaPaymentIntent,
) -> bool:
    loyalty_block = ""
    if intent.purchase_kind == PaymentKindEnum.SUBSCRIPTION:
        purchase = intent.payment.apple_cashback_purchase
        if purchase.rate_percent is None:
            return False
        if purchase.result_expired_at is None:
            raise RuntimeError("subscription_result_missing")
        slug = "proxy_purchased"
        context = {
            "expired_date": format_user_date(purchase.result_expired_at)
        }
        loyalty_block = _render_apple_cashback_block(purchase=purchase)
    elif intent.purchase_kind == PaymentKindEnum.VPN_SUBSCRIPTION:
        subscription = intent.payment.user.vpn_subscription
        slug = "crypto_vpn_purchased"
        context = {
            "expired_at": format_user_datetime(subscription.expired_at),
            "subscription_url": (
                f"{settings.VPN_SUBSCRIPTION_BASE_URL.rstrip('/')}"
                "/api/v1/vpn/subscriptions/"
                f"{subscription.token}/"
            ),
        }
    else:
        purchase = intent.payment.apple_cashback_purchase
        if purchase.rate_percent is None:
            return False
        slug = "crypto_gift_certificate_purchased"
        context = {"code": intent.payment.gift_certificate.code}
        loyalty_block = _render_apple_cashback_block(purchase=purchase)

    message = get_template(slug=slug).render(context=context)
    send_telegram_message(
        chat_id=int(intent.initiator.username),
        text=f"{message.text}{loyalty_block}",
        markup=message.markup,
    )
    return True


@shared_task(
    bind=True,
    autoretry_for=(CryptoPayClientError,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def reconcile_crypto_payments_task(self) -> dict[str, int]:
    """Reconcile stored Crypto Pay intents with bounded provider polling."""
    counters = get_reconcile_crypto_payments_service()()
    logger.info("crypto_reconciliation_complete", extra=counters)
    return counters


@shared_task(bind=True, max_retries=3)
def notify_crypto_purchase_task(self, intent_id: int) -> None:
    """Надёжно доставляет сохранённый результат Crypto Pay инициатору."""
    intent = get_crypto_intent_for_notification(intent_id=intent_id)
    if intent is None:
        return

    try:
        delivered = _send_purchase_result(intent=intent)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)

    if not delivered:
        return

    mark_crypto_notification_sent(
        intent_id=intent.pk,
        sent_at=timezone.now(),
    )


@shared_task(bind=True, max_retries=3)
def notify_platega_purchase_task(self, intent_id: int) -> None:
    """Надёжно доставляет сохранённый результат Platega SBP инициатору."""
    intent = get_platega_intent_for_notification(intent_id=intent_id)
    if intent is None:
        return

    delivery_failed = False
    delivered = False
    try:
        delivered = _send_purchase_result(intent=intent)
    except Exception:
        delivery_failed = True

    if delivery_failed:
        raise self.retry(
            exc=RuntimeError("platega_notification_delivery_failed"),
            countdown=30,
        ) from None

    if not delivered:
        return

    mark_platega_notification_sent(
        intent_id=intent.pk,
        sent_at=timezone.now(),
    )


@shared_task
def warn_crypto_webhook_admin_task(
    warning: dict[str, int | str | None],
) -> None:
    """Send only allowlisted identifiers for a rejected signed webhook."""
    safe = {
        key: warning.get(key)
        for key in ("reason", "update_id", "invoice_id", "intent_id")
    }
    send_telegram_message(
        chat_id=settings.MY_TELEGRAM_ID,
        text=(
            "⚠️ <b>Crypto Pay webhook rejected</b>\n"
            f"reason={escape(str(safe['reason']))} "
            f"update_id={escape(str(safe['update_id']))} "
            f"invoice_id={escape(str(safe['invoice_id']))} "
            f"intent_id={escape(str(safe['intent_id']))}"
        ),
        timeout=settings.TELEGRAM_TIMEOUT,
    )
