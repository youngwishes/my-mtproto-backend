from __future__ import annotations

from typing import Protocol

from apps.payments.services.dtos import (
    VPNPaymentFulfillmentIn,
    VPNPaymentFulfillmentOut,
)


class VPNPaymentFulfillment(Protocol):
    """Payment-owned contract implemented by the VPN composition root."""

    def __call__(
        self,
        *,
        purchase: VPNPaymentFulfillmentIn,
    ) -> VPNPaymentFulfillmentOut: ...
