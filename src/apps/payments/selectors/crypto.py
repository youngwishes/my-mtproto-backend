from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet

from apps.payments.enums import (
    CryptoPaymentIntentStatusEnum,
    PaymentKindEnum,
)
from apps.payments.models import (
    CryptoPaymentIntent,
)

if TYPE_CHECKING:
    from apps.payments.services.dtos.crypto_pay_dtos import CryptoInvoiceDTO


def get_reusable_crypto_intent(
    *, initiator_id: int, purchase_kind: str, now: datetime
) -> CryptoPaymentIntent | None:
    return CryptoPaymentIntent.objects.filter(
        initiator_id=initiator_id,
        purchase_kind=purchase_kind,
        status=CryptoPaymentIntentStatusEnum.ACTIVE,
        provider_expires_at__gt=now,
    ).first()


def get_creating_crypto_intent(
    *, initiator_id: int, purchase_kind: str
) -> CryptoPaymentIntent | None:
    return CryptoPaymentIntent.objects.filter(
        initiator_id=initiator_id,
        purchase_kind=purchase_kind,
        status=CryptoPaymentIntentStatusEnum.CREATING,
    ).first()


def create_crypto_intent(
    *,
    initiator_id: int,
    purchase_kind: str,
    product_code: str,
    rub_amount: Decimal,
    public_id: UUID,
) -> CryptoPaymentIntent:
    return CryptoPaymentIntent.objects.create(
        initiator_id=initiator_id,
        purchase_kind=purchase_kind,
        product_code=product_code,
        rub_amount=rub_amount,
        public_id=public_id,
    )


def get_crypto_intent_by_provider_invoice_id(
    *, provider_invoice_id: int
) -> CryptoPaymentIntent | None:
    return (
        CryptoPaymentIntent.objects.select_related("initiator", "payment")
        .filter(provider_invoice_id=provider_invoice_id)
        .first()
    )


def get_crypto_intent_by_id(*, intent_id: int) -> CryptoPaymentIntent | None:
    return (
        CryptoPaymentIntent.objects.select_related("initiator", "payment")
        .filter(pk=intent_id)
        .first()
    )


def get_crypto_intent_for_notification(*, intent_id: int) -> CryptoPaymentIntent | None:
    return (
        CryptoPaymentIntent.objects.select_related(
            "initiator",
            "payment",
            "payment__key",
            "payment__gift_certificate",
            "payment__apple_cashback_purchase",
            "payment__user__vpn_subscription",
        )
        .filter(
            pk=intent_id,
            status=CryptoPaymentIntentStatusEnum.FULFILLED,
            notification_sent_at__isnull=True,
        )
        .first()
    )


def get_unfinished_crypto_intents(*, limit: int) -> QuerySet[CryptoPaymentIntent]:
    return (
        CryptoPaymentIntent.objects.select_related("initiator")
        .filter(
            payment__isnull=True,
            status__in=(
                CryptoPaymentIntentStatusEnum.ACTIVE,
                CryptoPaymentIntentStatusEnum.LOCAL_EXPIRED,
                CryptoPaymentIntentStatusEnum.RETRYABLE,
            ),
        )
        .order_by("pk")[:limit]
    )


def get_unnotified_fulfilled_crypto_intents(
    *, limit: int
) -> QuerySet[CryptoPaymentIntent]:
    return (
        CryptoPaymentIntent.objects.select_related(
            "initiator",
            "payment",
            "payment__apple_cashback_purchase",
        )
        .filter(
            Q(purchase_kind=PaymentKindEnum.VPN_SUBSCRIPTION)
            | Q(payment__apple_cashback_purchase__rate_percent__isnull=False),
            status=CryptoPaymentIntentStatusEnum.FULFILLED,
            notification_sent_at__isnull=True,
        )
        .order_by("pk")[:limit]
    )


def conditionally_transition_crypto_intent(
    *,
    intent_id: int,
    from_statuses: tuple[str, ...],
    to_status: str,
    updates: dict[str, object],
) -> int:
    return CryptoPaymentIntent.objects.filter(
        pk=intent_id,
        status__in=from_statuses,
    ).update(status=to_status, **updates)


def claim_crypto_intent_for_fulfillment(
    *, intent_id: int, attempted_at: datetime
) -> int:
    return CryptoPaymentIntent.objects.filter(
        pk=intent_id,
        payment__isnull=True,
        status__in=(
            CryptoPaymentIntentStatusEnum.ACTIVE,
            CryptoPaymentIntentStatusEnum.LOCAL_EXPIRED,
            CryptoPaymentIntentStatusEnum.RETRYABLE,
        ),
    ).update(
        status=CryptoPaymentIntentStatusEnum.PROCESSING,
        fulfillment_attempted_at=attempted_at,
        updated_at=attempted_at,
    )


def finalize_crypto_intent_fulfillment(
    *, intent_id: int, payment_id: int, paid_at: datetime, fulfilled_at: datetime
) -> int:
    return CryptoPaymentIntent.objects.filter(
        pk=intent_id,
        payment__isnull=True,
        status=CryptoPaymentIntentStatusEnum.PROCESSING,
    ).update(
        payment_id=payment_id,
        paid_at=paid_at,
        fulfilled_at=fulfilled_at,
        status=CryptoPaymentIntentStatusEnum.FULFILLED,
        updated_at=fulfilled_at,
    )


def mark_crypto_intent_retryable(*, intent_id: int, error_code: str) -> int:
    return CryptoPaymentIntent.objects.filter(
        pk=intent_id,
        payment__isnull=True,
        status=CryptoPaymentIntentStatusEnum.PROCESSING,
    ).update(
        status=CryptoPaymentIntentStatusEnum.RETRYABLE,
        last_error_code=error_code,
    )


def mark_crypto_notification_sent(*, intent_id: int, sent_at: datetime) -> int:
    return CryptoPaymentIntent.objects.filter(
        pk=intent_id,
        status=CryptoPaymentIntentStatusEnum.FULFILLED,
        notification_sent_at__isnull=True,
    ).update(notification_sent_at=sent_at, updated_at=sent_at)


def mark_crypto_intent_provider_expired(*, intent_id: int) -> int:
    return CryptoPaymentIntent.objects.filter(
        pk=intent_id,
        status__in=(
            CryptoPaymentIntentStatusEnum.ACTIVE,
            CryptoPaymentIntentStatusEnum.LOCAL_EXPIRED,
        ),
    ).update(status=CryptoPaymentIntentStatusEnum.PROVIDER_EXPIRED)


def expire_active_crypto_intent(
    *, initiator_id: int, purchase_kind: str, now: datetime
) -> int:
    return CryptoPaymentIntent.objects.filter(
        initiator_id=initiator_id,
        purchase_kind=purchase_kind,
        status=CryptoPaymentIntentStatusEnum.ACTIVE,
        provider_expires_at__lte=now,
    ).update(status=CryptoPaymentIntentStatusEnum.LOCAL_EXPIRED, updated_at=now)


def fail_stale_creating_crypto_intent(
    *, initiator_id: int, purchase_kind: str, stale_before: datetime
) -> int:
    return CryptoPaymentIntent.objects.filter(
        initiator_id=initiator_id,
        purchase_kind=purchase_kind,
        status=CryptoPaymentIntentStatusEnum.CREATING,
        created_at__lte=stale_before,
    ).update(
        status=CryptoPaymentIntentStatusEnum.CREATE_FAILED,
        last_error_code="creating_stale",
    )


def reserve_crypto_intent_or_read_winner(
    *,
    initiator_id: int,
    purchase_kind: str,
    product_code: str,
    rub_amount: Decimal,
    public_id: UUID,
) -> tuple[CryptoPaymentIntent, bool]:
    try:
        with transaction.atomic():
            intent = create_crypto_intent(
                initiator_id=initiator_id,
                purchase_kind=purchase_kind,
                product_code=product_code,
                rub_amount=rub_amount,
                public_id=public_id,
            )
    except IntegrityError:
        winner = CryptoPaymentIntent.objects.filter(
            initiator_id=initiator_id,
            purchase_kind=purchase_kind,
            status__in=(
                CryptoPaymentIntentStatusEnum.CREATING,
                CryptoPaymentIntentStatusEnum.ACTIVE,
            ),
        ).first()
        if winner is None:
            raise
        return winner, False
    return intent, True


def fail_crypto_intent_creation(*, intent_id: int, error_code: str) -> int:
    return conditionally_transition_crypto_intent(
        intent_id=intent_id,
        from_statuses=(CryptoPaymentIntentStatusEnum.CREATING,),
        to_status=CryptoPaymentIntentStatusEnum.CREATE_FAILED,
        updates={"last_error_code": error_code},
    )


def activate_crypto_intent_from_provider(
    *, intent_id: int, invoice: CryptoInvoiceDTO
) -> CryptoPaymentIntent | None:
    updated_rows = conditionally_transition_crypto_intent(
        intent_id=intent_id,
        from_statuses=(CryptoPaymentIntentStatusEnum.CREATING,),
        to_status=CryptoPaymentIntentStatusEnum.ACTIVE,
        updates={
            "provider_invoice_id": invoice.invoice_id,
            "provider_invoice_url": invoice.bot_invoice_url,
            "provider_created_at": invoice.created_at,
            "provider_expires_at": invoice.expiration_date,
            "last_error_code": "",
        },
    )
    if updated_rows != 1:
        return None
    return CryptoPaymentIntent.objects.get(pk=intent_id)
