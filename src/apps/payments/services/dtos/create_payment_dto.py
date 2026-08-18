from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from apps.core.dtos import BaseServiceDTO
from apps.payments.services.dtos.apple_cashback_dtos import (
    ApplePurchaseOutcomeDTO,
    HistoricalPurchaseReplayDTO,
)


@dataclass(kw_only=True, frozen=True, slots=True)
class CreatePaymentIn(BaseServiceDTO):
    """Входные данные для создания платежа."""

    username: str
    charge_id: str
    provider: str
    nominal_rub_amount: Decimal | None = None


@dataclass(kw_only=True, frozen=True, slots=True)
class CreatePaymentOut(BaseServiceDTO):
    """Saved MTProxy fulfilment and loyalty outcome."""

    expired_date: str
    loyalty: ApplePurchaseOutcomeDTO


CreatePaymentResult = CreatePaymentOut | HistoricalPurchaseReplayDTO
