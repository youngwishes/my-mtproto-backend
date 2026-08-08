from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from time import sleep
from typing import TYPE_CHECKING, Callable, TypeVar, final
from uuid import uuid4

from django.conf import settings
from django.db import OperationalError
from django.utils import timezone

from apps.payments.clients import get_platega_client
from apps.payments.enums import (
    PaymentKindEnum,
    PaymentMethodCodeEnum,
    PlategaPaymentIntentStatusEnum,
    ProductCodeEnum,
)
from apps.payments.exceptions import (
    BadPaymentData,
    PlategaClientError,
    PlategaInvoiceCreationInProgress,
    PlategaInvoiceUnavailable,
    ProductNotFound,
)
from apps.payments.selectors import (
    activate_platega_intent_from_provider,
    expire_active_platega_intent,
    fail_platega_intent_creation,
    fail_stale_creating_platega_intent,
    get_active_product_by_code,
    get_blocking_platega_intent,
    get_payment_method_commission_percent,
    get_reusable_platega_intent,
    reserve_platega_intent_or_read_winner,
)
from apps.payments.services.dtos import CreatePlategaInvoiceIn, CreatePlategaInvoiceOut
from apps.users.selectors import get_user_by_username

if TYPE_CHECKING:
    from apps.payments.clients import PlategaClient
    from apps.payments.models import PlategaPaymentIntent


_PRODUCT_BY_KIND = {
    PaymentKindEnum.SUBSCRIPTION: ProductCodeEnum.MTPROTO_30D,
    PaymentKindEnum.VPN_SUBSCRIPTION: ProductCodeEnum.VPN_30D,
    PaymentKindEnum.GIFT_CERTIFICATE: ProductCodeEnum.MTPROTO_30D,
}
_DATABASE_LOCK_RETRIES = 5
_DATABASE_LOCK_RETRY_DELAY = 0.01
_ResultT = TypeVar("_ResultT")


def _intent_output(
    *, intent: PlategaPaymentIntent, reused: bool
) -> CreatePlategaInvoiceOut:
    assert intent.provider_expires_at is not None
    return CreatePlategaInvoiceOut(
        payment_url=intent.provider_payment_url,
        rub_amount=intent.rub_amount,
        expires_at=intent.provider_expires_at,
        reused=reused,
    )


def _retry_database_lock(*, operation: Callable[[], _ResultT]) -> _ResultT:
    for attempt in range(_DATABASE_LOCK_RETRIES):
        try:
            return operation()
        except OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == _DATABASE_LOCK_RETRIES - 1:
                raise
            sleep(_DATABASE_LOCK_RETRY_DELAY)
    raise AssertionError("unreachable")


def _fail_creation_or_raise(*, intent_id: int, error_code: str, username: str) -> None:
    try:
        _retry_database_lock(
            operation=lambda: fail_platega_intent_creation(
                intent_id=intent_id,
                error_code=error_code,
            )
        )
    except OperationalError:
        raise PlategaInvoiceUnavailable(username, reason_code="database_locked") from None


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class CreateOrReusePlategaInvoiceService:
    """Create one Platega SBP link or reuse the current live local intent."""

    platega_client: PlategaClient
    clock: Callable[[], datetime]
    commission_percent_selector: Callable[..., Decimal | None]

    def __call__(self, *, request: CreatePlategaInvoiceIn) -> CreatePlategaInvoiceOut:
        now = self.clock()
        try:
            user = get_user_by_username(username=request.username)
            if user is None or request.purchase_kind not in _PRODUCT_BY_KIND:
                raise BadPaymentData(request.username, reason_code="invalid_purchase")

            reusable = get_reusable_platega_intent(
                initiator_id=user.pk,
                purchase_kind=request.purchase_kind,
                now=now,
            )
            if reusable is not None:
                return _intent_output(intent=reusable, reused=True)

            expire_active_platega_intent(
                initiator_id=user.pk,
                purchase_kind=request.purchase_kind,
                now=now,
            )
            fail_stale_creating_platega_intent(
                initiator_id=user.pk,
                purchase_kind=request.purchase_kind,
                stale_before=now - timedelta(seconds=2 * settings.PLATEGA_REQUEST_TIMEOUT),
            )
            blocking = get_blocking_platega_intent(
                initiator_id=user.pk,
                purchase_kind=request.purchase_kind,
            )
            if blocking is not None:
                raise PlategaInvoiceCreationInProgress(
                    request.username,
                    reason_code=blocking.status,
                )
            product_code = _PRODUCT_BY_KIND[PaymentKindEnum(request.purchase_kind)]
            product = get_active_product_by_code(code=product_code)
            if product is None:
                raise ProductNotFound(request.username)
            kopecks = Decimal(product.price)
            if product.currency != "RUB":
                raise BadPaymentData(request.username, reason_code="invalid_currency")
            if kopecks <= 0 or kopecks != kopecks.to_integral_value():
                raise BadPaymentData(request.username, reason_code="invalid_price")
            user_amount = (kopecks / Decimal("100")).quantize(Decimal("0.01"))
            commission_percent = self.commission_percent_selector(
                code=PaymentMethodCodeEnum.PLATEGA_SBP
            )
            if commission_percent is None:
                raise PlategaInvoiceUnavailable(
                    request.username,
                    reason_code="payment_method_unavailable",
                )
            provider_amount = (
                user_amount
                / (Decimal("1") + commission_percent / Decimal("100"))
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            intent, created = reserve_platega_intent_or_read_winner(
                initiator_id=user.pk,
                purchase_kind=request.purchase_kind,
                product_code=product_code,
                rub_amount=user_amount,
                public_id=uuid4(),
            )
        except PlategaInvoiceCreationInProgress:
            raise
        except OperationalError as exc:
            raise PlategaInvoiceUnavailable(
                request.username,
                reason_code=(
                    "database_locked" if "locked" in str(exc).lower() else "database_error"
                ),
            ) from None

        if not created:
            if (
                intent.status == PlategaPaymentIntentStatusEnum.ACTIVE
                and intent.provider_expires_at is not None
                and intent.provider_expires_at > now
            ):
                return _intent_output(intent=intent, reused=True)
            raise PlategaInvoiceCreationInProgress(
                request.username,
                reason_code="creating",
            )

        try:
            provider_transaction = self.platega_client.create_transaction(
                amount=provider_amount,
                description=product.title,
                return_url=settings.BOT_LINK,
                public_id=intent.public_id,
                telegram_id=user.username,
                telegram_username=user.telegram_username or user.username,
            )
        except PlategaClientError as exc:
            error_code = str(exc)
            _fail_creation_or_raise(
                intent_id=intent.pk,
                error_code=error_code,
                username=request.username,
            )
            raise PlategaInvoiceUnavailable(request.username, reason_code=error_code) from None

        try:
            activated = _retry_database_lock(
                operation=lambda: activate_platega_intent_from_provider(
                    intent_id=intent.pk,
                    transaction=provider_transaction,
                    expires_at=now + provider_transaction.expires_in,
                )
            )
        except OperationalError:
            _fail_creation_or_raise(
                intent_id=intent.pk,
                error_code="database_locked",
                username=request.username,
            )
            raise PlategaInvoiceUnavailable(
                request.username,
                reason_code="database_locked",
            ) from None
        if activated is None:
            raise PlategaInvoiceUnavailable(request.username, reason_code="creation_lost")
        return _intent_output(intent=activated, reused=False)


def get_create_or_reuse_platega_invoice_service() -> CreateOrReusePlategaInvoiceService:
    """Build the Platega create/reuse service from backend-only dependencies."""
    return CreateOrReusePlategaInvoiceService(
        platega_client=get_platega_client(),
        clock=timezone.now,
        commission_percent_selector=get_payment_method_commission_percent,
    )
