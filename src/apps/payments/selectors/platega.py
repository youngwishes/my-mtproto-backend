from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Q

from apps.payments.enums import (
    PaymentKindEnum,
    PlategaPaymentIntentStatusEnum,
)
from apps.payments.models import (
    PlategaPaymentIntent,
)

if TYPE_CHECKING:
    from apps.payments.services.dtos.platega_dtos import PlategaTransactionDTO


def get_reusable_platega_intent(
    *, initiator_id: int, purchase_kind: str, now: datetime
) -> PlategaPaymentIntent | None:
    return PlategaPaymentIntent.objects.filter(
        initiator_id=initiator_id,
        purchase_kind=purchase_kind,
        status=PlategaPaymentIntentStatusEnum.ACTIVE,
        provider_expires_at__gt=now,
    ).first()


def get_blocking_platega_intent(
    *, initiator_id: int, purchase_kind: str
) -> PlategaPaymentIntent | None:
    return PlategaPaymentIntent.objects.filter(
        initiator_id=initiator_id,
        purchase_kind=purchase_kind,
        status__in=(
            PlategaPaymentIntentStatusEnum.CREATING,
            PlategaPaymentIntentStatusEnum.PROCESSING,
            PlategaPaymentIntentStatusEnum.RETRYABLE,
        ),
    ).first()


def expire_active_platega_intent(
    *, initiator_id: int, purchase_kind: str, now: datetime
) -> int:
    return PlategaPaymentIntent.objects.filter(
        initiator_id=initiator_id,
        purchase_kind=purchase_kind,
        status=PlategaPaymentIntentStatusEnum.ACTIVE,
        provider_expires_at__lte=now,
    ).update(status=PlategaPaymentIntentStatusEnum.LOCAL_EXPIRED, updated_at=now)


def fail_stale_creating_platega_intent(
    *, initiator_id: int, purchase_kind: str, stale_before: datetime
) -> int:
    return PlategaPaymentIntent.objects.filter(
        initiator_id=initiator_id,
        purchase_kind=purchase_kind,
        status=PlategaPaymentIntentStatusEnum.CREATING,
        created_at__lte=stale_before,
    ).update(
        status=PlategaPaymentIntentStatusEnum.CREATE_FAILED,
        last_error_code="creating_stale",
    )


def create_platega_intent(
    *,
    initiator_id: int,
    purchase_kind: str,
    product_code: str,
    rub_amount: Decimal,
    public_id: UUID,
) -> PlategaPaymentIntent:
    return PlategaPaymentIntent.objects.create(
        initiator_id=initiator_id,
        purchase_kind=purchase_kind,
        product_code=product_code,
        rub_amount=rub_amount,
        public_id=public_id,
    )


def reserve_platega_intent_or_read_winner(
    *,
    initiator_id: int,
    purchase_kind: str,
    product_code: str,
    rub_amount: Decimal,
    public_id: UUID,
) -> tuple[PlategaPaymentIntent, bool]:
    try:
        with transaction.atomic():
            intent = create_platega_intent(
                initiator_id=initiator_id,
                purchase_kind=purchase_kind,
                product_code=product_code,
                rub_amount=rub_amount,
                public_id=public_id,
            )
    except IntegrityError:
        winner = PlategaPaymentIntent.objects.filter(
            initiator_id=initiator_id,
            purchase_kind=purchase_kind,
            status__in=(
                PlategaPaymentIntentStatusEnum.CREATING,
                PlategaPaymentIntentStatusEnum.ACTIVE,
            ),
        ).first()
        if winner is None:
            raise
        return winner, False
    return intent, True


def fail_platega_intent_creation(*, intent_id: int, error_code: str) -> int:
    return PlategaPaymentIntent.objects.filter(
        pk=intent_id,
        status=PlategaPaymentIntentStatusEnum.CREATING,
    ).update(
        status=PlategaPaymentIntentStatusEnum.CREATE_FAILED,
        last_error_code=error_code,
    )


def activate_platega_intent_from_provider(
    *,
    intent_id: int,
    transaction: PlategaTransactionDTO,
    expires_at: datetime,
) -> PlategaPaymentIntent | None:
    updated_rows = PlategaPaymentIntent.objects.filter(
        pk=intent_id,
        status=PlategaPaymentIntentStatusEnum.CREATING,
    ).update(
        status=PlategaPaymentIntentStatusEnum.ACTIVE,
        provider_transaction_id=transaction.transaction_id,
        provider_payment_url=transaction.redirect_url,
        provider_expires_at=expires_at,
        last_error_code="",
        updated_at=expires_at,
    )
    if updated_rows == 1:
        return PlategaPaymentIntent.objects.get(pk=intent_id)
    return PlategaPaymentIntent.objects.filter(
        pk=intent_id,
        status=PlategaPaymentIntentStatusEnum.ACTIVE,
        provider_transaction_id=transaction.transaction_id,
        provider_payment_url=transaction.redirect_url,
        provider_expires_at=expires_at,
    ).first()


def get_platega_intent_by_provider_transaction_id(
    *, provider_transaction_id: UUID
) -> PlategaPaymentIntent | None:
    return (
        PlategaPaymentIntent.objects.select_related("initiator", "payment")
        .filter(provider_transaction_id=provider_transaction_id)
        .first()
    )


def cancel_platega_intent(*, intent_id: int, canceled_at: datetime) -> int:
    return PlategaPaymentIntent.objects.filter(
        pk=intent_id,
        status__in=(
            PlategaPaymentIntentStatusEnum.ACTIVE,
            PlategaPaymentIntentStatusEnum.LOCAL_EXPIRED,
        ),
    ).update(
        status=PlategaPaymentIntentStatusEnum.PROVIDER_CANCELED,
        updated_at=canceled_at,
    )


def get_platega_intent_by_id(*, intent_id: int) -> PlategaPaymentIntent | None:
    return (
        PlategaPaymentIntent.objects.select_related("initiator", "payment")
        .filter(pk=intent_id)
        .first()
    )


def get_platega_intent_for_notification(
    *, intent_id: int
) -> PlategaPaymentIntent | None:
    return (
        PlategaPaymentIntent.objects.select_related(
            "initiator",
            "payment",
            "payment__key",
            "payment__gift_certificate",
            "payment__apple_cashback_purchase",
            "payment__user__vpn_subscription",
        )
        .filter(
            pk=intent_id,
            payment__isnull=False,
            status=PlategaPaymentIntentStatusEnum.FULFILLED,
            notification_queued_at__isnull=False,
            notification_sent_at__isnull=True,
        )
        .first()
    )


def mark_platega_notification_sent(*, intent_id: int, sent_at: datetime) -> int:
    return PlategaPaymentIntent.objects.filter(
        pk=intent_id,
        status=PlategaPaymentIntentStatusEnum.FULFILLED,
        notification_sent_at__isnull=True,
    ).update(notification_sent_at=sent_at, updated_at=sent_at)


def claim_platega_intent_for_fulfillment(
    *, intent_id: int, attempted_at: datetime
) -> int:
    return PlategaPaymentIntent.objects.filter(
        pk=intent_id,
        payment__isnull=True,
        status__in=(
            PlategaPaymentIntentStatusEnum.ACTIVE,
            PlategaPaymentIntentStatusEnum.LOCAL_EXPIRED,
            PlategaPaymentIntentStatusEnum.RETRYABLE,
        ),
    ).update(
        status=PlategaPaymentIntentStatusEnum.PROCESSING,
        fulfillment_attempted_at=attempted_at,
        updated_at=attempted_at,
    )


def finalize_platega_intent_fulfillment(
    *, intent_id: int, payment_id: int, fulfilled_at: datetime
) -> int:
    return PlategaPaymentIntent.objects.filter(
        pk=intent_id,
        payment__isnull=True,
        status=PlategaPaymentIntentStatusEnum.PROCESSING,
    ).update(
        payment_id=payment_id,
        fulfilled_at=fulfilled_at,
        status=PlategaPaymentIntentStatusEnum.FULFILLED,
        last_error_code="",
        updated_at=fulfilled_at,
    )


def mark_platega_intent_retryable(*, intent_id: int, error_code: str) -> int:
    return PlategaPaymentIntent.objects.filter(
        pk=intent_id,
        payment__isnull=True,
        status__in=(
            PlategaPaymentIntentStatusEnum.ACTIVE,
            PlategaPaymentIntentStatusEnum.LOCAL_EXPIRED,
            PlategaPaymentIntentStatusEnum.PROCESSING,
            PlategaPaymentIntentStatusEnum.RETRYABLE,
        ),
    ).update(
        status=PlategaPaymentIntentStatusEnum.RETRYABLE,
        last_error_code=error_code,
    )


def claim_platega_notification_enqueue(*, intent_id: int, queued_at: datetime) -> int:
    return PlategaPaymentIntent.objects.filter(
        Q(purchase_kind=PaymentKindEnum.VPN_SUBSCRIPTION)
        | Q(payment__apple_cashback_purchase__rate_percent__isnull=False),
        pk=intent_id,
        status=PlategaPaymentIntentStatusEnum.FULFILLED,
        notification_queued_at__isnull=True,
    ).update(notification_queued_at=queued_at, updated_at=queued_at)


def clear_platega_notification_enqueue(*, intent_id: int, queued_at: datetime) -> int:
    return PlategaPaymentIntent.objects.filter(
        pk=intent_id,
        status=PlategaPaymentIntentStatusEnum.FULFILLED,
        notification_queued_at=queued_at,
    ).update(notification_queued_at=None)
