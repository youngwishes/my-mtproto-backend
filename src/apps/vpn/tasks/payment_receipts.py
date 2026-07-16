from __future__ import annotations

import uuid

from celery import shared_task

from apps.vpn.factories.payment_receipts import (
    get_payment_writer_lock,
    get_recover_payment_receipts_service as _get_recovery_service,
    get_retry_payment_receipt_service,
    get_vpn_payment_receipt_service,
)
from apps.vpn.exceptions import VPNPaymentReceiptApplyFailed
from apps.vpn.services import RecoverPaymentReceiptsService


def _enqueue_receipt(*, receipt_id: int, countdown: float) -> None:
    apply_payment_receipt_task.apply_async(
        kwargs={"receipt_id": receipt_id},
        countdown=countdown,
    )


def get_recover_payment_receipts_service() -> RecoverPaymentReceiptsService:
    return _get_recovery_service(enqueue_receipt=_enqueue_receipt)


@shared_task(name="apps.vpn.apply_payment_receipt")
def apply_payment_receipt_task(*, receipt_id: int) -> None:
    """Apply one receipt only while this process owns the shared writer lock."""
    retry_service = get_retry_payment_receipt_service()
    with get_payment_writer_lock()() as acquired:
        if not acquired:
            raise RuntimeError("vpn payment writer lock is held by another process")
        lease_id = uuid.uuid4()
        try:
            get_vpn_payment_receipt_service()(
                receipt_id=receipt_id,
                lease_id=lease_id,
            )
        except Exception as error:
            try:
                retry_service(
                    receipt_id=receipt_id,
                    lease_id=lease_id,
                    error=error,
                )
            except Exception:
                # A later recovery pass owns retrying a lease-handler failure.
                pass
            raise VPNPaymentReceiptApplyFailed() from None


@shared_task(name="apps.vpn.recover_payment_receipts")
def recover_payment_receipts_task() -> int:
    """Run one bounded recovery pass from the default worker."""
    return get_recover_payment_receipts_service()()
