from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.payments.models import PaymentIntent, PaymentReceipt


@dataclass(kw_only=True, slots=True, frozen=True)
class PaymentIntentData:
    user_id: int
    product_id: int
    currency: str
    amount: int
    provider: str

    def matches(self, *, intent: PaymentIntent) -> bool:
        return (
            self.user_id == intent.user_id
            and self.product_id == intent.product_id
            and self.currency == intent.currency
            and self.amount == intent.amount
            and self.provider == intent.provider
        )


@dataclass(kw_only=True, slots=True, frozen=True)
class PaymentReceiptData:
    intent_id: int
    user_id: int
    product_id: int
    provider: str
    charge_id: str
    currency: str
    amount: int

    def matches(self, *, receipt: PaymentReceipt) -> bool:
        return (
            self.intent_id == receipt.intent_id
            and self.user_id == receipt.user_id
            and self.product_id == receipt.product_id
            and self.provider == receipt.provider
            and self.charge_id == receipt.charge_id
            and self.currency == receipt.currency
            and self.amount == receipt.amount
        )
