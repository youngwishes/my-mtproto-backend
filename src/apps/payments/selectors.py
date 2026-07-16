from __future__ import annotations

from django.db import connection
from django.db.models import Count

from apps.payments.enums import PaymentKindEnum, ProductCodeEnum
from apps.payments.models import GiftCertificate, Payment, Product


def get_active_product_by_code(*, code: ProductCodeEnum) -> Product | None:
    """Return the active product matching an exact stable code."""
    return Product.objects.active().filter(code=code).first()


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
