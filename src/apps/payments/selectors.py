from __future__ import annotations

from apps.payments.enums import PaymentKindEnum
from apps.payments.models import GiftCertificate, Payment, Product


def get_active_product_by_code(*, code: str) -> Product | None:
    return Product.objects.active().filter(code=code).first()


def get_vpn_payment_by_identity_for_update(
    *,
    provider: str,
    charge_id: str,
) -> Payment | None:
    """VPN-платёж с блокировкой строки для идемпотентной обработки."""
    return (
        Payment.objects.select_for_update()
        .filter(
            provider=provider,
            charge_id=charge_id,
            kind=PaymentKindEnum.VPN_SUBSCRIPTION,
        )
        .first()
    )


def get_vpn_payment_by_identity(*, provider: str, charge_id: str) -> Payment | None:
    """VPN-платёж по identity провайдера."""
    return Payment.objects.filter(
        provider=provider,
        charge_id=charge_id,
        kind=PaymentKindEnum.VPN_SUBSCRIPTION,
    ).first()


def create_vpn_payment(
    *,
    user_id: int,
    provider: str,
    charge_id: str,
) -> Payment:
    """Сохраняет успешный платёж VPN без связи с MTProto-ключом."""
    return Payment.objects.create(
        user_id=user_id,
        key=None,
        provider=provider,
        charge_id=charge_id,
        kind=PaymentKindEnum.VPN_SUBSCRIPTION,
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
