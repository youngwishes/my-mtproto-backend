from __future__ import annotations

from decimal import Decimal

from django.db.models import Case, IntegerField, When

from apps.payments.enums import (
    PaymentKindEnum,
    PaymentMethodCodeEnum,
)
from apps.payments.models import (
    Payment,
    PaymentMethod,
    Product,
)
from apps.users.models import SystemUser

_SUPPORTED_PAYMENT_METHOD_CODES = (
    PaymentMethodCodeEnum.PLATEGA_SBP,
    PaymentMethodCodeEnum.STARS,
    PaymentMethodCodeEnum.CRYPTO_PAY,
)


def get_active_payment_method_codes() -> tuple[str, ...]:
    order = Case(
        When(code=PaymentMethodCodeEnum.PLATEGA_SBP, then=0),
        When(code=PaymentMethodCodeEnum.STARS, then=1),
        When(code=PaymentMethodCodeEnum.CRYPTO_PAY, then=2),
        output_field=IntegerField(),
    )
    return tuple(
        PaymentMethod.objects.active()
        .filter(code__in=_SUPPORTED_PAYMENT_METHOD_CODES)
        .order_by(order)
        .values_list("code", flat=True)
    )


def get_active_priority_payment_method_codes() -> tuple[str, ...]:
    order = Case(
        When(code=PaymentMethodCodeEnum.PLATEGA_SBP, then=0),
        When(code=PaymentMethodCodeEnum.STARS, then=1),
        When(code=PaymentMethodCodeEnum.CRYPTO_PAY, then=2),
        output_field=IntegerField(),
    )
    return tuple(
        PaymentMethod.objects.active()
        .filter(is_priority=True, code__in=_SUPPORTED_PAYMENT_METHOD_CODES)
        .order_by(order)
        .values_list("code", flat=True)
    )


def get_payment_method_commission_percent(*, code: str) -> Decimal | None:
    return (
        PaymentMethod.objects.filter(code=code)
        .values_list("commission_percent", flat=True)
        .first()
    )


def get_active_product_by_code(*, code: str) -> Product | None:
    return Product.objects.active().filter(code=code).first()


def get_payment_user_for_update(*, username: str) -> SystemUser | None:
    """Return the payment owner while locking their mutable loyalty state."""
    return SystemUser.objects.select_for_update().filter(username=username).first()


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


def get_payment_by_identity(
    *, provider: str, charge_id: str, kind: str
) -> Payment | None:
    return Payment.objects.filter(
        provider=provider,
        charge_id=charge_id,
        kind=kind,
    ).first()


def create_subscription_payment(
    *, user_id: int, key_id: int, charge_id: str, provider: str
) -> Payment:
    return Payment.objects.create(
        user_id=user_id,
        key_id=key_id,
        charge_id=charge_id,
        provider=provider,
        kind=PaymentKindEnum.SUBSCRIPTION,
    )
