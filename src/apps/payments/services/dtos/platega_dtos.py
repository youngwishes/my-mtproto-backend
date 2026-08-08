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
