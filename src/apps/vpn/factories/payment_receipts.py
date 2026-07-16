from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from django.conf import settings

from apps.payments.services import (
    ApplyPaymentReceiptService,
    get_apply_payment_receipt_service,
)
from apps.vpn.services.fulfill_purchase import (
    get_fulfill_purchase_service,
    register_after_commit as _register_after_commit,
)
from apps.vpn.infra import FileSingleWriterLock, VPNPaymentWorkerHealthCheck
from apps.vpn.services.recover_payment_receipts import (
    RecoverPaymentReceiptsService,
    get_recover_payment_receipts_service as _get_recovery_service,
)
from apps.vpn.services.retry_payment_receipt import (
    RetryPaymentReceiptService,
    get_retry_payment_receipt_service as _get_retry_service,
)


def _defer_delivery_to_reconcile(*, access_id: int) -> None:
    """Accelerate delivery; hourly full reconcile recovers a lost enqueue."""
    from apps.vpn.tasks.reconcile import reconcile_vpn_nodes_task

    reconcile_vpn_nodes_task.delay()


def get_vpn_payment_receipt_service(
    *,
    schedule_delivery: Callable[..., None] = _defer_delivery_to_reconcile,
    register_after_commit: Callable[
        [Callable[[], None]], None
    ] = _register_after_commit,
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


def get_payment_writer_lock() -> FileSingleWriterLock:
    return FileSingleWriterLock(path=Path(settings.VPN_PAYMENT_WRITER_LOCK_PATH))


def get_payment_worker_health_check() -> VPNPaymentWorkerHealthCheck:
    return VPNPaymentWorkerHealthCheck(
        lock_path=Path(settings.VPN_PAYMENT_WORKER_OWNER_LOCK_PATH),
        pid_path=Path(settings.VPN_PAYMENT_WORKER_OWNER_PID_PATH),
    )


def get_recover_payment_receipts_service(
    *,
    enqueue_receipt: Callable[..., None],
) -> RecoverPaymentReceiptsService:
    return _get_recovery_service(enqueue_receipt=enqueue_receipt)


def get_retry_payment_receipt_service() -> RetryPaymentReceiptService:
    return _get_retry_service(
        base_delay_seconds=settings.VPN_PAYMENT_RETRY_BASE_SECONDS,
        max_delay_seconds=settings.VPN_PAYMENT_RETRY_MAX_SECONDS,
        jitter_max_seconds=settings.VPN_PAYMENT_RETRY_JITTER_SECONDS,
    )
