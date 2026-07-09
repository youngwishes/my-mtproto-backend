from __future__ import annotations

from apps.payments.enums import PaymentKindEnum
from apps.payments.models import GiftCertificate


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
