from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol, final

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.payments.enums import (
    PaymentIntentStatusEnum,
    PaymentProviderEnum,
    ProductCodeEnum,
)
from apps.payments.exceptions import (
    BadPaymentData,
    PaymentIntentExpired,
    PaymentIntentMismatch,
    PaymentIntentNotFound,
    VPNProductNotConfigured,
)
from apps.payments.models import PaymentIntent
from apps.payments.selectors import (
    get_active_product_by_code,
    get_payment_intent_by_payload,
)
from apps.payments.services.dtos import ApprovedPaymentIntentOut, PaymentIntentOut
from apps.users.selectors import get_user_by_username

if TYPE_CHECKING:
    from apps.payments.models import Product
    from apps.payments.services.dtos import (
        CreatePaymentIntentIn,
        PreCheckoutPaymentIntentIn,
    )
    from apps.users.models import SystemUser


class SaleAvailability(Protocol):
    def __call__(self, *, customer: SystemUser) -> None: ...


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class CreatePaymentIntentService:
    """Create a short-lived immutable intent after a fail-closed sale check."""

    check_sale_availability: SaleAvailability
    get_product: Callable[..., Product | None]
    get_user: Callable[..., SystemUser | None]
    now: Callable[[], datetime]
    intent_ttl: timedelta

    def __call__(self, *, intent: CreatePaymentIntentIn) -> PaymentIntentOut:
        user = self.get_user(username=intent.username)
        if user is None:
            raise BadPaymentData(intent.username)
        self.check_sale_availability(customer=user)
        product = self.get_product(code=ProductCodeEnum.VLESS_30D)
        if not self._is_product_configured(product=product):
            raise VPNProductNotConfigured(intent.username)
        currency, amount, provider = self._commercial_identity(
            telegram_id=intent.username,
            currency=intent.currency,
            product=product,
        )
        created = PaymentIntent.objects.create(
            user=user,
            product=product,
            currency=currency,
            amount=amount,
            provider=provider,
            expires_at=self.now() + self.intent_ttl,
        )
        return PaymentIntentOut(
            intent_id=created.pk,
            invoice_payload=created.invoice_payload,
            currency=created.currency,
            amount=created.amount,
            provider=created.provider,
            expires_at=created.expires_at,
            title=product.title,
            description=product.description,
            provider_data=product.provider_data_json,
            send_email_to_provider=product.send_email_to_provider,
            need_email=product.need_email,
        )

    def _is_product_configured(self, *, product: Product | None) -> bool:
        return bool(
            product is not None
            and product.code == ProductCodeEnum.VLESS_30D
            and product.currency == "RUB"
            and product.price > 0
            and product.stars_price > 0
        )

    def _commercial_identity(
        self,
        *,
        telegram_id: str,
        currency: str,
        product: Product,
    ) -> tuple[str, int, PaymentProviderEnum]:
        if currency == "RUB":
            return (
                currency,
                int(Decimal(product.price) * 100),
                PaymentProviderEnum.YUKASSA,
            )
        if currency == "XTR":
            return currency, product.stars_price, PaymentProviderEnum.STARS
        raise BadPaymentData(telegram_id)


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ApprovePaymentIntentService:
    """Atomically approve an exact active intent after rechecking availability."""

    check_sale_availability: SaleAvailability
    get_intent: Callable[..., PaymentIntent | None]
    now: Callable[[], datetime]

    def __call__(
        self,
        *,
        pre_checkout: PreCheckoutPaymentIntentIn,
    ) -> ApprovedPaymentIntentOut:
        intent = self.get_intent(invoice_payload=pre_checkout.invoice_payload)
        if intent is None:
            raise PaymentIntentNotFound(pre_checkout.username)
        if not self._matches(pre_checkout=pre_checkout, intent=intent):
            raise PaymentIntentMismatch(pre_checkout.username)
        if intent.status == PaymentIntentStatusEnum.APPROVED:
            return self._result(intent=intent)
        if intent.status != PaymentIntentStatusEnum.CREATED:
            raise PaymentIntentMismatch(pre_checkout.username)
        if intent.expires_at <= self.now():
            raise PaymentIntentExpired(pre_checkout.username)

        self.check_sale_availability(customer=intent.user)
        with transaction.atomic():
            try:
                intent.transition_to(status=PaymentIntentStatusEnum.APPROVED)
            except ValidationError as exc:
                intent.refresh_from_db()
                if intent.status != PaymentIntentStatusEnum.APPROVED:
                    raise PaymentIntentMismatch(pre_checkout.username) from exc
        return self._result(intent=intent)

    def _matches(
        self,
        *,
        pre_checkout: PreCheckoutPaymentIntentIn,
        intent: PaymentIntent,
    ) -> bool:
        expected_provider = {
            "RUB": PaymentProviderEnum.YUKASSA,
            "XTR": PaymentProviderEnum.STARS,
        }.get(pre_checkout.currency)
        return (
            intent.user.username == pre_checkout.username
            and intent.product.code == ProductCodeEnum.VLESS_30D
            and intent.currency == pre_checkout.currency
            and intent.amount == pre_checkout.amount
            and intent.provider == expected_provider
        )

    def _result(self, *, intent: PaymentIntent) -> ApprovedPaymentIntentOut:
        return ApprovedPaymentIntentOut(intent_id=intent.pk, status=intent.status)


def get_create_payment_intent_service(
    *, check_sale_availability: SaleAvailability
) -> CreatePaymentIntentService:
    return CreatePaymentIntentService(
        check_sale_availability=check_sale_availability,
        get_product=get_active_product_by_code,
        get_user=get_user_by_username,
        now=timezone.now,
        intent_ttl=timedelta(seconds=settings.VPN_PAYMENT_INTENT_TTL_SECONDS),
    )


def get_approve_payment_intent_service(
    *, check_sale_availability: SaleAvailability
) -> ApprovePaymentIntentService:
    return ApprovePaymentIntentService(
        check_sale_availability=check_sale_availability,
        get_intent=get_payment_intent_by_payload,
        now=timezone.now,
    )
