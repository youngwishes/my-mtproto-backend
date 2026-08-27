from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING


from apps.payments.enums import (
    PaymentKindEnum,
)
from apps.payments.models import (
    GiftCertificate,
    Payment,
)

if TYPE_CHECKING:
    pass


def normalize_gift_certificate_code(*, code: str) -> str:
    return code.strip().upper()


def get_gift_certificate_by_code(*, code: str) -> GiftCertificate | None:
    return (
        GiftCertificate.objects.filter(
            code=normalize_gift_certificate_code(code=code),
        )
        .select_related("buyer", "payment", "activated_by")
        .first()
    )


def get_gift_certificate_by_payment_identity(
    *,
    provider: str,
    charge_id: str,
) -> GiftCertificate | None:
    return (
        GiftCertificate.objects.filter(
            payment__kind=PaymentKindEnum.GIFT_CERTIFICATE,
            payment__provider=provider,
            payment__charge_id=charge_id,
        )
        .select_related("buyer", "payment", "activated_by")
        .first()
    )


def create_gift_certificate_payment(
    *, user_id: int, provider: str, charge_id: str
) -> Payment:
    """Persist one successful gift-certificate payment."""
    return Payment.objects.create(
        user_id=user_id,
        key=None,
        charge_id=charge_id,
        provider=provider,
        kind=PaymentKindEnum.GIFT_CERTIFICATE,
    )


def create_gift_certificate(
    *, code: str, buyer_id: int, payment_id: int, expires_at: datetime
) -> GiftCertificate:
    """Persist the gift result owned by its paying buyer."""
    return GiftCertificate.objects.create(
        code=code,
        buyer_id=buyer_id,
        payment_id=payment_id,
        expires_at=expires_at,
    )
