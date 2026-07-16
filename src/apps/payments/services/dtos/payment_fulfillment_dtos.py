from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(kw_only=True, slots=True, frozen=True)
class VPNPaymentFulfillmentIn:
    receipt_id: int
    payment_id: int
    user_id: int
    accepted_at: datetime


@dataclass(kw_only=True, slots=True, frozen=True)
class VPNPaymentFulfillmentOut:
    access_id: int
    purchase_id: int


@dataclass(kw_only=True, slots=True, frozen=True)
class AppliedPaymentReceiptOut:
    receipt_id: int
    payment_id: int
    access_id: int | None
    purchase_id: int | None
    is_replay: bool
