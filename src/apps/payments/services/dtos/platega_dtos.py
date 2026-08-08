from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, slots=True, frozen=True)
class PlategaTransactionDTO(BaseServiceDTO):
    """Validated usable response from Platega transaction creation."""

    transaction_id: UUID
    status: str
    redirect_url: str
    expires_in: timedelta


@dataclass(kw_only=True, slots=True, frozen=True)
class CreatePlategaInvoiceIn(BaseServiceDTO):
    """Bot-originated request for a Platega invoice."""

    username: str
    purchase_kind: str


@dataclass(kw_only=True, slots=True, frozen=True)
class CreatePlategaInvoiceOut(BaseServiceDTO):
    """Safe Platega invoice data returned to the bot boundary."""

    payment_url: str
    rub_amount: Decimal
    expires_at: datetime
    reused: bool


@dataclass(kw_only=True, slots=True, frozen=True)
class PlategaCallbackDTO(BaseServiceDTO):
    """Normalized authenticated Platega callback fields."""

    transaction_id: UUID
    amount: Decimal
    currency: str
    status: str
    payment_method: int


@dataclass(kw_only=True, slots=True, frozen=True)
class ValidatedPlategaPaymentDTO(BaseServiceDTO):
    """Exact confirmed Platega transaction bound to its local intent."""

    intent_id: int
    transaction_id: UUID


@dataclass(kw_only=True, slots=True, frozen=True)
class PlategaCallbackWarningDTO(BaseServiceDTO):
    """Allowlisted callback rejection context safe for structured logging."""

    reason_code: str
    intent_id: int | None
    provider_transaction_id: UUID | None


@dataclass(kw_only=True, slots=True, frozen=True)
class ValidatePlategaCallbackOut(BaseServiceDTO):
    """Safe callback validation disposition."""

    payment: ValidatedPlategaPaymentDTO | None
    reason_code: str
    warning: PlategaCallbackWarningDTO | None


@dataclass(kw_only=True, slots=True, frozen=True)
class ApplyPlategaPaymentOut(BaseServiceDTO):
    """Idempotent Platega fulfilment disposition."""

    fulfilled: bool
    already_fulfilled: bool
