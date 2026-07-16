from __future__ import annotations

import time
from collections.abc import Callable

from apps.payments.services import (
    ApplyPaymentReceiptService,
    get_apply_payment_receipt_service,
)
from apps.vpn.services.fulfill_purchase import (
    get_fulfill_purchase_service,
    register_after_commit as _register_after_commit,
)


def get_vpn_payment_receipt_service(
    *,
    schedule_delivery: Callable[..., None],
    register_after_commit: Callable[[Callable[[], None]], None] = _register_after_commit,
    sleep: Callable[[float], None] = time.sleep,
) -> ApplyPaymentReceiptService:
    """Compose the payment owner with the concrete VPN fulfillment contract."""
    fulfillment = get_fulfill_purchase_service(
        schedule_delivery=schedule_delivery,
        register_after_commit_callback=register_after_commit,
    )
    return get_apply_payment_receipt_service(
        fulfill_purchase=fulfillment,
        sleep=sleep,
    )
