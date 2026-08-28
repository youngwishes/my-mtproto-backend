from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from time import sleep
from typing import TYPE_CHECKING, Callable, TypeVar, final
from urllib.parse import urlsplit
from uuid import uuid4

from django.conf import settings
from django.db import OperationalError
from django.utils import timezone

from apps.payments.clients import get_crypto_pay_client
from apps.payments.enums import (
    CryptoPaymentIntentStatusEnum,
    PaymentKindEnum,
    ProductCodeEnum,
)
from apps.payments.exceptions import (
    BadPaymentData,
    CryptoInvoiceCreationInProgress,
    CryptoInvoiceUnavailable,
    CryptoPayClientError,
    ProductNotFound,
)
from apps.payments.selectors.common import (
    get_active_product_by_code,
)
from apps.payments.selectors.crypto import (
    activate_crypto_intent_from_provider,
    expire_active_crypto_intent,
    fail_crypto_intent_creation,
    fail_stale_creating_crypto_intent,
    get_reusable_crypto_intent,
    reserve_crypto_intent_or_read_winner,
)
from apps.payments.services.dtos import (
    CreateCryptoInvoiceIn,
    CreateCryptoInvoiceOut,
    CryptoInvoiceDTO,
)
from apps.users.selectors import get_user_by_username

if TYPE_CHECKING:
    from apps.payments.clients import CryptoPayClient
    from apps.payments.models import CryptoPaymentIntent


_PRODUCT_BY_KIND = {
    PaymentKindEnum.SUBSCRIPTION: ProductCodeEnum.MTPROTO_30D,
    PaymentKindEnum.VPN_SUBSCRIPTION: ProductCodeEnum.VPN_30D,
    PaymentKindEnum.GIFT_CERTIFICATE: ProductCodeEnum.MTPROTO_30D,
}
_DATABASE_LOCK_RETRIES = 5
_DATABASE_LOCK_RETRY_DELAY = 0.01
_ResultT = TypeVar("_ResultT")


def _intent_output(
    *, intent: CryptoPaymentIntent, reused: bool
) -> CreateCryptoInvoiceOut:
    return CreateCryptoInvoiceOut(
        invoice_url=intent.provider_invoice_url,
        rub_amount=intent.rub_amount,
        expires_at=intent.provider_expires_at,
        reused=reused,
    )


def _is_aware_datetime(value: object) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def _is_usable_https_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == "https"
            and bool(parsed.netloc)
            and parsed.hostname is not None
        )
    except ValueError:
        return False


def _created_invoice_error_code(
    *,
    invoice: CryptoInvoiceDTO,
    intent: CryptoPaymentIntent,
    requested_amount: Decimal,
) -> str | None:
    if type(invoice.invoice_id) is not int or invoice.invoice_id <= 0:
        return "create_invoice_id_invalid"
    if invoice.status != "active":
        return "create_status_invalid"
    if invoice.payload != str(intent.public_id):
        return "create_payload_mismatch"
    if invoice.currency_type != "fiat":
        return "create_currency_type_mismatch"
    if invoice.fiat != "RUB":
        return "create_fiat_mismatch"
    if invoice.amount != requested_amount:
        return "create_amount_mismatch"
    if invoice.accepted_assets != frozenset({"USDT", "TON"}):
        return "create_assets_mismatch"
    if invoice.paid_asset is not None or invoice.paid_at is not None:
        return "create_already_paid"
    if not _is_usable_https_url(invoice.bot_invoice_url):
        return "create_url_invalid"
    if not (
        _is_aware_datetime(invoice.created_at)
        and _is_aware_datetime(invoice.expiration_date)
    ):
        return "create_timestamp_invalid"
    if invoice.expiration_date <= invoice.created_at:
        return "create_expiration_invalid"
    return None


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
            operation=lambda: fail_crypto_intent_creation(intent_id=intent_id, error_code=error_code)
        )
    except OperationalError as exc:
        if "locked" not in str(exc).lower():
            raise
        raise CryptoInvoiceUnavailable(username, reason_code="database_locked") from exc


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class CreateOrReuseCryptoInvoiceService:
    """Create one validated Crypto Pay invoice or reuse its live local intent."""

    crypto_pay_client: CryptoPayClient
    clock: Callable[[], datetime]

    def __call__(
        self, *, request: CreateCryptoInvoiceIn
    ) -> CreateCryptoInvoiceOut:
        now = self.clock()
        user = get_user_by_username(username=request.username)
        if user is None or request.purchase_kind not in _PRODUCT_BY_KIND:
            raise BadPaymentData(request.username, reason_code="invalid_purchase")

        reusable = get_reusable_crypto_intent(
            initiator_id=user.pk,
            purchase_kind=request.purchase_kind,
            now=now,
        )
        if reusable is not None:
            return _intent_output(intent=reusable, reused=True)

        try:
            expire_active_crypto_intent(
                initiator_id=user.pk,
                purchase_kind=request.purchase_kind,
                now=now,
            )
            fail_stale_creating_crypto_intent(
                initiator_id=user.pk,
                purchase_kind=request.purchase_kind,
                stale_before=now
                - timedelta(seconds=2 * settings.CRYPTOPAY_REQUEST_TIMEOUT),
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
            amount = (kopecks / Decimal("100")).quantize(Decimal("0.01"))

            intent, created = reserve_crypto_intent_or_read_winner(
                initiator_id=user.pk,
                purchase_kind=request.purchase_kind,
                product_code=product_code,
                rub_amount=amount,
                public_id=uuid4(),
            )
        except OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            raise CryptoInvoiceCreationInProgress(
                request.username,
                reason_code="creating",
            ) from exc
        if not created:
            if (
                intent.status == CryptoPaymentIntentStatusEnum.ACTIVE
                and intent.provider_expires_at is not None
                and intent.provider_expires_at > now
            ):
                return _intent_output(intent=intent, reused=True)
            raise CryptoInvoiceCreationInProgress(
                request.username,
                reason_code="creating",
            )

        try:
            invoice = self.crypto_pay_client.create_invoice(
                amount=amount,
                payload=str(intent.public_id),
                description=product.title,
            )
        except CryptoPayClientError as exc:
            error_code = str(exc)
            _fail_creation_or_raise(intent_id=intent.pk, error_code=error_code, username=request.username)
            raise CryptoInvoiceUnavailable(
                request.username,
                reason_code=error_code,
            ) from exc

        error_code = _created_invoice_error_code(
            invoice=invoice,
            intent=intent,
            requested_amount=amount,
        )
        if error_code is not None:
            _fail_creation_or_raise(intent_id=intent.pk, error_code=error_code, username=request.username)
            raise CryptoInvoiceUnavailable(
                request.username,
                reason_code=error_code,
            )
        try:
            activated = _retry_database_lock(
                operation=lambda: activate_crypto_intent_from_provider(
                    intent_id=intent.pk, invoice=invoice
                )
            )
        except OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            _fail_creation_or_raise(intent_id=intent.pk, error_code="database_locked", username=request.username)
            raise CryptoInvoiceUnavailable(request.username, reason_code="database_locked") from exc
        if activated is None:
            raise CryptoInvoiceUnavailable(
                request.username,
                reason_code="creation_lost",
            )
        return _intent_output(intent=activated, reused=False)


def get_create_or_reuse_crypto_invoice_service() -> CreateOrReuseCryptoInvoiceService:
    """Build the create/reuse service with backend-only provider settings."""
    return CreateOrReuseCryptoInvoiceService(
        crypto_pay_client=get_crypto_pay_client(),
        clock=timezone.now,
    )
