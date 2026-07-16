from __future__ import annotations

from datetime import datetime

from django.db import connection
from django.db.models import Count, Q, QuerySet

from apps.payments.enums import (
    PaymentKindEnum,
    PaymentReceiptStatusEnum,
    ProductCodeEnum,
)
from apps.payments.models import (
    GiftCertificate,
    Payment,
    PaymentIntent,
    PaymentReceipt,
    Product,
)


def get_active_product_by_code(*, code: ProductCodeEnum) -> Product | None:
    """Return the active product matching an exact stable code."""
    return Product.objects.active().filter(code=code).first()


def get_payment_intent_by_payload(*, invoice_payload: str) -> PaymentIntent | None:
    """Return an intent only for an exact unpredictable invoice payload."""
    return (
        PaymentIntent.objects.filter(invoice_payload=invoice_payload)
        .select_related("user", "product")
        .first()
    )


def get_payment_receipt_by_identity(
    *,
    provider: str,
    charge_id: str,
) -> PaymentReceipt | None:
    """Return the durable receipt for an exact provider payment identity."""
    return (
        PaymentReceipt.objects.filter(provider=provider, charge_id=charge_id)
        .select_related("intent", "user", "product", "payment")
        .first()
    )


def get_payment_receipt_by_intent_id(*, intent_id: int) -> PaymentReceipt | None:
    """Return the sole durable receipt already accepted for an intent."""
    return (
        PaymentReceipt.objects.filter(intent_id=intent_id)
        .select_related("intent", "user", "product", "payment")
        .first()
    )


def get_payment_by_identity(*, provider: str, charge_id: str) -> Payment | None:
    """Expose an existing legacy/new Payment before receipt identity acceptance."""
    return (
        Payment.objects.filter(provider=provider, charge_id=charge_id)
        .select_related("user", "product")
        .first()
    )


def get_recoverable_payment_receipts(
    *,
    due_at: datetime,
    stale_before: datetime,
) -> QuerySet[PaymentReceipt]:
    """Return received, due retry and stale leased receipts for recovery."""
    return PaymentReceipt.objects.filter(
        Q(status=PaymentReceiptStatusEnum.RECEIVED)
        | Q(
            status=PaymentReceiptStatusEnum.RETRY,
            next_attempt_at__lte=due_at,
        )
        | Q(
            status=PaymentReceiptStatusEnum.PROCESSING,
            processing_started_at__lte=stale_before,
        )
    ).order_by("accepted_at", "pk")


def get_product_preflight_rows() -> list[tuple[int, str | None, bool]]:
    """Return only non-commercial Product fields safe for preflight output."""
    with connection.cursor() as cursor:
        columns = {
            column.name
            for column in connection.introspection.get_table_description(
                cursor, Product._meta.db_table
            )
        }
    code_field_exists = "code" in columns
    if code_field_exists:
        return list(Product.objects.order_by("pk").values_list("pk", "code", "is_active"))
    return [
        (product_pk, None, is_active)
        for product_pk, is_active in Product.objects.order_by("pk").values_list(
            "pk", "is_active"
        )
    ]


def get_duplicate_non_empty_payment_identity_count() -> int:
    """Count duplicate provider identities without returning sensitive values."""
    return (
        Payment.objects.exclude(charge_id="")
        .values("provider", "charge_id")
        .annotate(identity_count=Count("pk"))
        .filter(identity_count__gt=1)
        .count()
    )


def normalize_gift_certificate_code(*, code: str) -> str:
    return code.strip().upper()


def get_gift_certificate_by_code(*, code: str) -> GiftCertificate | None:
    return GiftCertificate.objects.filter(
        code=normalize_gift_certificate_code(code=code),
    ).select_related("buyer", "payment", "activated_by").first()


def get_gift_certificate_by_payment_identity(
    *,
    provider: str,
    charge_id: str,
) -> GiftCertificate | None:
    return GiftCertificate.objects.filter(
        payment__kind=PaymentKindEnum.GIFT_CERTIFICATE,
        payment__provider=provider,
        payment__charge_id=charge_id,
    ).select_related("buyer", "payment", "activated_by").first()
