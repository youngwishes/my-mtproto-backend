from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from apps.core.dtos import BaseServiceDTO


@dataclass(kw_only=True, slots=True, frozen=True)
class CreatePaymentIntentIn(BaseServiceDTO):
    username: str
    currency: str


@dataclass(kw_only=True, slots=True, frozen=True)
class PaymentIntentOut(BaseServiceDTO):
    intent_id: int
    invoice_payload: str
    currency: str
    amount: int
    provider: str
    expires_at: datetime


@dataclass(kw_only=True, slots=True, frozen=True)
class PreCheckoutPaymentIntentIn(BaseServiceDTO):
    username: str
    invoice_payload: str
    currency: str
    amount: int


@dataclass(kw_only=True, slots=True, frozen=True)
class ApprovedPaymentIntentOut(BaseServiceDTO):
    intent_id: int
    status: str


@dataclass(kw_only=True, slots=True, frozen=True)
class AcceptPaymentReceiptIn(BaseServiceDTO):
    username: str
    invoice_payload: str
    provider: str
    charge_id: str
    currency: str
    amount: int


@dataclass(kw_only=True, slots=True, frozen=True)
class AcceptedPaymentReceiptOut(BaseServiceDTO):
    receipt_id: int
    status: str
    is_replay: bool
