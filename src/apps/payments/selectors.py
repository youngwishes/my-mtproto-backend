from __future__ import annotations

from datetime import datetime

from django.db import connection
from django.db import models
from django.db.models import Count, Q, QuerySet
from django.db.models.functions import Coalesce, Greatest

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


def get_payment_receipt_by_id(*, receipt_id: int) -> PaymentReceipt | None:
    """Return a receipt and immutable relations used by the apply transaction."""
    return (
        PaymentReceipt.objects.filter(pk=receipt_id)
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


def get_vpn_receipt_observability_summary(
    *,
    at: datetime,
    stale_before: datetime,
    alert_limit: int = 100,
) -> dict[str, object]:
    """Aggregate historical receipts in SQL and bound alert cardinality."""
    receipts = PaymentReceipt.objects.filter(
        product__code=ProductCodeEnum.VLESS_30D
    ).annotate(
        effective_applied_at=Coalesce("applied_at", "updated_at"),
    ).annotate(
        effective_ready_at=Coalesce(
            "ready_at",
            Greatest(
                "effective_applied_at",
                "payment__vpn_purchase__access__updated_at",
            ),
        )
    )
    unapplied = ~Q(status=PaymentReceiptStatusEnum.APPLIED)
    apply_duration = models.ExpressionWrapper(
        models.F("effective_applied_at") - models.F("accepted_at"),
        output_field=models.DurationField(),
    )
    readiness_duration = models.ExpressionWrapper(
        models.F("effective_ready_at") - models.F("effective_applied_at"),
        output_field=models.DurationField(),
    )
    summary = receipts.aggregate(
        received_count=Count(
            "pk", filter=Q(status=PaymentReceiptStatusEnum.RECEIVED)
        ),
        processing_count=Count(
            "pk", filter=Q(status=PaymentReceiptStatusEnum.PROCESSING)
        ),
        retry_count=Count("pk", filter=Q(status=PaymentReceiptStatusEnum.RETRY)),
        applied_count=Count(
            "pk", filter=Q(status=PaymentReceiptStatusEnum.APPLIED)
        ),
        attempts_sum=Coalesce(models.Sum("attempt_count"), 0),
        oldest_unapplied_at=models.Min("accepted_at", filter=unapplied),
        stale_count=Count(
            "pk", filter=unapplied & Q(accepted_at__lte=stale_before)
        ),
        max_apply_duration=models.Max(
            apply_duration,
            filter=Q(status=PaymentReceiptStatusEnum.APPLIED),
        ),
        max_readiness_duration=models.Max(
            readiness_duration,
            filter=Q(
                status=PaymentReceiptStatusEnum.APPLIED,
                ready_at__isnull=False,
            )
            | Q(
                status=PaymentReceiptStatusEnum.APPLIED,
                ready_at__isnull=True,
                payment__vpn_purchase__access__state="ready",
                payment__vpn_purchase__access__updated_at__isnull=False,
            ),
        ),
    )
    summary["stale_receipt_ids"] = tuple(
        receipts.filter(unapplied, accepted_at__lte=stale_before)
        .order_by("accepted_at", "pk")
        .values_list("pk", flat=True)[:alert_limit]
    )
    return summary


def mark_latest_vpn_receipt_ready(*, access_id: int, ready_at: datetime) -> bool:
    """Mark only the newest applied receipt waiting on this access transition."""
    receipt_id = (
        PaymentReceipt.objects.filter(
            status=PaymentReceiptStatusEnum.APPLIED,
            ready_at__isnull=True,
            payment__vpn_purchase__access_id=access_id,
        )
        .order_by("-accepted_at", "-pk")
        .values_list("pk", flat=True)
        .first()
    )
    if receipt_id is None:
        return False
    return bool(
        PaymentReceipt.objects.filter(pk=receipt_id, ready_at__isnull=True)._safe_update(
            ready_at=ready_at
        )
    )


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
